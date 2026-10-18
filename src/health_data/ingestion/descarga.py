"""Descarga robusta y validada de fuentes de datos (INEGI, CONEVAL, Salud).

Maneja reintentos con retroceso exponencial, reanudación con cabecera Range,
validación de firmas ZIP, y detección de respuestas engañosas de INEGI (HTTP 200 con HTML).
"""

from __future__ import annotations

import logging
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from health_data.config import RAW_DATA_DIR, ensure_directories

log = logging.getLogger(__name__)

CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/zip,application/octet-stream,*/*",
}

FIRMA_ZIP = b"PK\x03\x04"
TAMANO_MINIMO_VALIDO = 50_000  # 50 KB mínimo para considerar que no es un error de texto
REINTENTOS = 3


class ErrorDeDescarga(RuntimeError):
    """Fallo en la descarga por causas transitorias (red, timeout)."""


class ContenidoInvalido(ErrorDeDescarga, RuntimeError):
    """El servidor entregó un archivo inválido (ej. HTML en vez de ZIP)."""


@dataclass
class ResultadoDescarga:
    """Resultado estructurado de una descarga."""

    dataset_id: str
    ruta: Path
    bytes_descargados: int
    reutilizado: bool
    segundos: float


def _parece_html(ruta: Path) -> bool:
    """Detecta si el archivo es en realidad una página de error en HTML."""
    try:
        with ruta.open("rb") as fh:
            inicio = fh.read(512).lower()
            return b"<html" in inicio or b"<!doctype" in inicio
    except OSError:
        return False


def _validar_zip(ruta: Path, dataset_id: str, tamano_minimo: int = TAMANO_MINIMO_VALIDO) -> None:
    """Valida la integridad de un archivo ZIP."""
    if not ruta.exists():
        raise ContenidoInvalido(f"[{dataset_id}] No se encontró el archivo: {ruta}")

    tamano = ruta.stat().st_size
    if tamano < tamano_minimo:
        if _parece_html(ruta):
            raise ContenidoInvalido(
                f"[{dataset_id}] El servidor entregó una página HTML de error ({tamano} bytes). "
                f"La URL probablemente ya no existe o cambió."
            )
        raise ContenidoInvalido(
            f"[{dataset_id}] El archivo pesa {tamano} bytes, inferior al mínimo esperado ({tamano_minimo})."
        )

    with ruta.open("rb") as fh:
        if fh.read(4) != FIRMA_ZIP:
            raise ContenidoInvalido(
                f"[{dataset_id}] El archivo {ruta.name} no tiene firma válida de ZIP (PK)."
            )

    try:
        with zipfile.ZipFile(ruta) as zf:
            corrupto = zf.testzip()
            if corrupto is not None:
                raise ContenidoInvalido(
                    f"[{dataset_id}] El ZIP está corrupto en el elemento: {corrupto!r}"
                )
    except zipfile.BadZipFile as exc:
        raise ContenidoInvalido(f"[{dataset_id}] Archivo ZIP no legible: {exc}") from exc


def _tamano_remoto(sesion: requests.Session, url: str) -> int | None:
    """Consulta el encabezado Content-Length del servidor si está disponible."""
    try:
        respuesta = sesion.head(url, timeout=30, allow_redirects=True)
        if respuesta.status_code >= 400:
            return None
        declarado = respuesta.headers.get("Content-Length")
        return int(declarado) if declarado else None
    except (requests.RequestException, ValueError):
        return None


def descargar_dataset(
    dataset_id: str,
    url: str,
    nombre_archivo: str,
    *,
    forzar: bool = False,
    destino_dir: Path | None = None,
    tamano_minimo: int = TAMANO_MINIMO_VALIDO,
    max_segundos: float | None = None,
) -> ResultadoDescarga:
    """Descarga un dataset al directorio raw con validación y reintentos.

    Si el archivo termina en .zip, se verifica su firma e integridad.
    """
    ensure_directories()
    carpeta = destino_dir or RAW_DATA_DIR
    destino = carpeta / nombre_archivo
    parcial = destino.with_suffix(destino.suffix + ".part")
    inicio = time.monotonic()

    es_zip = nombre_archivo.lower().endswith(".zip")

    if destino.exists() and not forzar:
        if es_zip:
            _validar_zip(destino, dataset_id, tamano_minimo=tamano_minimo)
        log.info("[%s] Archivo ya presente y validado: %s", dataset_id, destino.name)
        return ResultadoDescarga(
            dataset_id=dataset_id,
            ruta=destino,
            bytes_descargados=destino.stat().st_size,
            reutilizado=True,
            segundos=0.0,
        )

    with requests.Session() as sesion:
        sesion.headers.update(CABECERAS)
        # Si el servidor reporta Content-Length pequeño y es HTML, cortar de inmediato
        # Si no es HTML, se procede a descargar con streaming y validar el archivo resultante
        tamano_remoto = _tamano_remoto(sesion, url)

        ultimo_error: Exception | None = None
        for intento in range(1, REINTENTOS + 1):
            try:
                ya_descargado = parcial.stat().st_size if parcial.exists() else 0
                cabeceras = dict(sesion.headers)
                if ya_descargado:
                    cabeceras["Range"] = f"bytes={ya_descargado}-"
                    log.info(
                        "[%s] Reanudando descarga en %s MB (intento %s/%s)",
                        dataset_id,
                        round(ya_descargado / 1e6, 2),
                        intento,
                        REINTENTOS,
                    )
                else:
                    log.info(
                        "[%s] Descargando %s (intento %s/%s)",
                        dataset_id,
                        nombre_archivo,
                        intento,
                        REINTENTOS,
                    )

                modo = "ab" if ya_descargado else "wb"
                with sesion.get(url, headers=cabeceras, stream=True, timeout=120) as resp:
                    if resp.status_code == 416:  # Range fuera de rango, ya completo
                        resp.raise_for_status()
                    elif ya_descargado and resp.status_code == 200:
                        log.warning(
                            "[%s] El servidor ignoró Range; reiniciando descarga desde 0.",
                            dataset_id,
                        )
                        modo = "wb"
                    elif resp.status_code not in (200, 206):
                        resp.raise_for_status()

                    with parcial.open(modo) as fh:
                        for bloque in resp.iter_content(chunk_size=1 << 20):
                            if not bloque:
                                continue
                            fh.write(bloque)
                            if (
                                max_segundos is not None
                                and (time.monotonic() - inicio) > max_segundos
                            ):
                                raise TimeoutError(
                                    f"[{dataset_id}] Límite de tiempo excedido ({max_segundos:.0f} s)."
                                )

                parcial.replace(destino)
                if es_zip:
                    _validar_zip(destino, dataset_id, tamano_minimo=tamano_minimo)

                segundos = time.monotonic() - inicio
                log.info(
                    "[%s] Descarga completa: %s MB en %.1f s",
                    dataset_id,
                    round(destino.stat().st_size / 1e6, 2),
                    segundos,
                )
                return ResultadoDescarga(
                    dataset_id=dataset_id,
                    ruta=destino,
                    bytes_descargados=destino.stat().st_size,
                    reutilizado=False,
                    segundos=segundos,
                )

            except ContenidoInvalido:
                if destino.exists():
                    destino.unlink(missing_ok=True)
                raise

            except (requests.RequestException, TimeoutError, ErrorDeDescarga) as exc:
                ultimo_error = exc
                log.warning(
                    "[%s] Falló intento %s/%s: %s", dataset_id, intento, REINTENTOS, exc
                )
                if intento < REINTENTOS:
                    time.sleep(2**intento)
                if destino.exists():
                    destino.unlink(missing_ok=True)

    raise ErrorDeDescarga(
        f"[{dataset_id}] No se pudo descargar tras {REINTENTOS} intentos: {ultimo_error}"
    )
