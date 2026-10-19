"""Descarga, validación y registro de las fuentes de datos (INEGI, CONEVAL, Salud).

- Reintentos con retroceso exponencial y reanudación con cabecera Range.
- Validación: firma e integridad de los ZIP; los .xlsx además deben ser un libro de
  Excel. Detecta respuestas engañosas (HTTP 200 con una página HTML de error).
- Registro: cada descarga nueva queda en catalog/ingestions.csv con su huella SHA-256,
  y references/fuentes_descargadas.md describe la última descarga de cada fuente.
- Un archivo que ya existe no se vuelve a descargar; si su huella no es la registrada,
  se detiene en vez de usarlo.

Uso: ``make download FUENTE=SALUD-001`` para una fuente, o ``make data`` para todas.
Las fuentes y sus descripciones están en config/fuentes_health.yaml.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

from health_data.config import (
    PROJECT_ROOT,
    RAW_DATA_DIR,
    FuenteInfo,
    cargar_configuracion,
    ensure_directories,
)

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

REGISTRO = PROJECT_ROOT / "catalog" / "ingestions.csv"
DESCRIPCION = PROJECT_ROOT / "references" / "fuentes_descargadas.md"
COLUMNAS_REGISTRO = [
    "ingestion_id",
    "dataset_id",
    "retrieved_at",
    "raw_path",
    "checksum",
    "status",
    "notes",
    "download_url",
]


class ErrorDeDescarga(RuntimeError):
    """Fallo en la descarga por causas transitorias (red, timeout)."""


class ContenidoInvalido(ErrorDeDescarga, RuntimeError):
    """El servidor entregó un archivo inválido (ej. HTML en vez de ZIP) o el crudo cambió."""


# Nombre usado por la primera versión del registro de descargas
ArchivoInvalido = ContenidoInvalido


@dataclass
class ResultadoDescarga:
    """Resultado estructurado de una descarga."""

    dataset_id: str
    ruta: Path
    bytes_descargados: int
    reutilizado: bool
    segundos: float
    checksum: str = ""
    registrada: bool = False


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


def _validar_xlsx(ruta: Path, dataset_id: str, tamano_minimo: int = TAMANO_MINIMO_VALIDO) -> None:
    """Valida que el archivo sea un libro de Excel completo (un ZIP con xl/workbook.xml)."""
    _validar_zip(ruta, dataset_id, tamano_minimo=tamano_minimo)
    with zipfile.ZipFile(ruta) as libro:
        if "xl/workbook.xml" not in libro.namelist():
            raise ContenidoInvalido(f"[{dataset_id}] El ZIP {ruta.name} no es un libro de Excel.")


# Validación por formato. Un formato nuevo necesita su función aquí.
VALIDADORES = {
    "zip": _validar_zip,
    "xlsx": _validar_xlsx,
}


def validar(
    ruta: Path,
    formato: str | None = None,
    *,
    dataset_id: str = "",
    tamano_minimo: int = TAMANO_MINIMO_VALIDO,
) -> None:
    """Valida el archivo según su formato (por omisión, el de su extensión)."""
    formato = (formato or ruta.suffix.lstrip(".")).lower()
    if formato in VALIDADORES:
        VALIDADORES[formato](ruta, dataset_id or ruta.name, tamano_minimo=tamano_minimo)
    elif not ruta.exists() or ruta.stat().st_size == 0 or _parece_html(ruta):
        raise ContenidoInvalido(f"[{dataset_id or ruta.name}] El archivo está vacío o es una página HTML.")


def huella(ruta: Path) -> str:
    """Huella SHA-256 del archivo, con el prefijo ``sha256:``."""
    with ruta.open("rb") as archivo:
        return "sha256:" + hashlib.file_digest(archivo, "sha256").hexdigest()


def _ruta_relativa(ruta: Path) -> str:
    """Ruta relativa a la raíz del proyecto, con diagonales (o absoluta si está fuera)."""
    try:
        return ruta.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return ruta.as_posix()


def leer_registro() -> list[dict[str, str]]:
    """Descargas registradas en catalog/ingestions.csv."""
    if not REGISTRO.exists():
        return []
    with REGISTRO.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def ultimo_registro(ruta: Path) -> dict[str, str] | None:
    """Última fila registrada del archivo, o None si no tiene."""
    filas = [f for f in leer_registro() if f["raw_path"] == _ruta_relativa(ruta)]
    return filas[-1] if filas else None


def registrar(dataset_id: str, url: str, ruta: Path, checksum: str) -> None:
    """Agrega la descarga a catalog/ingestions.csv (lo crea con su encabezado si no existe)."""
    fecha = datetime.now().astimezone()
    fila = {
        "ingestion_id": f"{dataset_id}_{fecha:%Y%m%dT%H%M%S}",
        "dataset_id": dataset_id,
        "retrieved_at": fecha.isoformat(timespec="seconds"),
        "raw_path": _ruta_relativa(ruta),
        "checksum": checksum,
        "status": "ok",
        "notes": "",
        "download_url": url,
    }
    nuevo = not REGISTRO.exists()
    if nuevo:
        REGISTRO.parent.mkdir(parents=True, exist_ok=True)
        columnas = COLUMNAS_REGISTRO
    else:
        with REGISTRO.open(newline="", encoding="utf-8") as archivo:
            columnas = next(csv.reader(archivo))
    with REGISTRO.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, columnas, lineterminator="\n", extrasaction="ignore")
        if nuevo:
            escritor.writeheader()
        escritor.writerow(fila)


def _revisar_existente(ruta: Path, dataset_id: str) -> str:
    """Compara la huella de un archivo existente con su último registro y la devuelve."""
    actual = huella(ruta)
    registro = ultimo_registro(ruta)
    if registro is None:
        log.info("[%s] %s no está en el registro de descargas (%s).", dataset_id, ruta.name, actual)
    elif registro["checksum"] != actual:
        raise ContenidoInvalido(
            f"[{dataset_id}] {ruta.name} ya existe, pero su huella no es la registrada el "
            f"{registro['retrieved_at']}. Revise si el crudo cambió; para volver a descargarlo, "
            f"bórrelo o use --forzar."
        )
    return actual


def escribir_descripcion(fuentes: dict[str, FuenteInfo] | None = None) -> None:
    """Describe la última descarga de cada fuente en references/fuentes_descargadas.md."""
    fuentes = fuentes if fuentes is not None else cargar_configuracion().fuentes
    ultimas = {fila["raw_path"]: fila for fila in leer_registro()}
    lineas = [
        "# Fuentes descargadas",
        "",
        "Archivo generado por `health_data.ingestion.descarga` a partir de "
        "`catalog/ingestions.csv`. No editar a mano.",
    ]
    for fuente in fuentes.values():
        if not fuente.nombre_archivo:
            continue
        fila = ultimas.get(_ruta_relativa(RAW_DATA_DIR / fuente.nombre_archivo))
        if fila is None:
            continue
        fecha = datetime.fromisoformat(fila["retrieved_at"])
        lineas += ["", f"## {fuente.dataset_id}: {fuente.nombre}"]
        if fuente.descripcion:
            lineas += ["", fuente.descripcion]
        lineas += [""]
        if fuente.institucion:
            lineas += [f"- Fuente: {fuente.institucion}"]
        lineas += [
            f"- Descarga: {fila.get('download_url') or fuente.url}",
            f"- Fecha de descarga: {fecha:%d/%m/%Y %H:%M}",
            f"- Archivo crudo: `{fila['raw_path']}`",
            f"- SHA-256: `{fila['checksum'].removeprefix('sha256:')}`",
        ]
        if fuente.nota:
            lineas += ["", fuente.nota]
    DESCRIPCION.parent.mkdir(parents=True, exist_ok=True)
    DESCRIPCION.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def _registrar_si_es_nueva(dataset_id: str, url: str, ruta: Path) -> tuple[str, bool]:
    """Registra la descarga salvo que sea idéntica a la última registrada."""
    actual = huella(ruta)
    registro = ultimo_registro(ruta)
    if registro and registro["checksum"] == actual:
        log.info(
            "[%s] Idéntica a la descarga registrada el %s; no se agrega fila.",
            dataset_id, registro["retrieved_at"],
        )
        return actual, False
    registrar(dataset_id, url, ruta, actual)
    escribir_descripcion()
    return actual, True


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
    """Descarga un dataset al directorio raw con validación, reintentos y registro.

    Los .zip y .xlsx se validan por firma e integridad. Cada descarga nueva se registra
    en catalog/ingestions.csv con su huella, salvo que sea idéntica a la última.
    """
    ensure_directories()
    carpeta = destino_dir or RAW_DATA_DIR
    destino = carpeta / nombre_archivo
    parcial = destino.with_suffix(destino.suffix + ".part")
    inicio = time.monotonic()

    if destino.exists() and not forzar:
        validar(destino, dataset_id=dataset_id, tamano_minimo=tamano_minimo)
        checksum = _revisar_existente(destino, dataset_id)
        log.info("[%s] Archivo ya presente y validado: %s", dataset_id, destino.name)
        return ResultadoDescarga(
            dataset_id=dataset_id,
            ruta=destino,
            bytes_descargados=destino.stat().st_size,
            reutilizado=True,
            segundos=0.0,
            checksum=checksum,
        )

    with requests.Session() as sesion:
        sesion.headers.update(CABECERAS)

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
                validar(destino, dataset_id=dataset_id, tamano_minimo=tamano_minimo)
                checksum, registrada = _registrar_si_es_nueva(dataset_id, url, destino)

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
                    checksum=checksum,
                    registrada=registrada,
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


def fuentes_descargables() -> dict[str, FuenteInfo]:
    """Fuentes aprobadas con URL y archivo en config/fuentes_health.yaml."""
    return {
        dataset_id: f
        for dataset_id, f in cargar_configuracion().fuentes.items()
        if f.estado == "approved" and f.url and f.nombre_archivo
    }


def main(argv: list[str] | None = None) -> int:
    """Descarga una fuente a data/raw, la valida y la registra."""
    fuentes = fuentes_descargables()
    parser = argparse.ArgumentParser(
        prog="python -m health_data.ingestion.descarga",
        description="Descarga una fuente a data/raw y la registra en catalog/ingestions.csv.",
    )
    parser.add_argument("dataset_id", choices=sorted(fuentes), help="por ejemplo, SALUD-001")
    parser.add_argument("--forzar", action="store_true", help="Descarga aunque el archivo ya exista.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    fuente = fuentes[args.dataset_id]
    print(f"{fuente.dataset_id}: {fuente.nombre_archivo}")
    try:
        res = descargar_dataset(fuente.dataset_id, fuente.url, fuente.nombre_archivo, forzar=args.forzar)
    except ErrorDeDescarga as exc:
        print(f"  Error: {exc}", file=sys.stderr)
        return 1

    estado = "ya existía" if res.reutilizado else f"descargado ({res.bytes_descargados:,} bytes)"
    print(f"  {_ruta_relativa(res.ruta)}: {estado}")
    print(f"  Huella: {res.checksum}")
    if res.registrada:
        print(f"  Registrado en {_ruta_relativa(REGISTRO)}; descripción en {_ruta_relativa(DESCRIPCION)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
