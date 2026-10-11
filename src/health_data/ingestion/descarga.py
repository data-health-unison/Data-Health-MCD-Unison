"""Descarga a data/raw una fuente de fuentes.FUENTES y registra la descarga."""

import argparse
import csv
import hashlib
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests

from health_data.ingestion.fuentes import FUENTES, Fuente
from health_data.pipeline import PROJECT_ROOT, RAW_DATA_DIR, ensure_directories


REGISTRO = PROJECT_ROOT / "catalog" / "ingestions.csv"
DESCRIPCION = PROJECT_ROOT / "references" / "fuentes_descargadas.md"

INTENTOS = 3
ESPERA_REINTENTO = 5  # Segundos; se duplica en cada intento.
TIEMPO_LIMITE = (15, 120)  # Segundos para conectar y para recibir cada bloque.
TAMANO_BLOQUE = 1024 * 1024
ENCABEZADOS = {
    "User-Agent": "health-data/0.1 (proyecto academico, Universidad de Sonora)"
}


class ArchivoInvalido(Exception):
    """El archivo está vacío, no tiene el formato esperado o cambió."""


def ruta_relativa(ruta: Path) -> str:
    """Devuelve la ruta relativa a la raíz del proyecto, con diagonales."""
    return ruta.relative_to(PROJECT_ROOT).as_posix()


def huella(ruta: Path) -> str:
    """Calcula la huella SHA-256 del archivo."""
    with ruta.open("rb") as archivo:
        return "sha256:" + hashlib.file_digest(archivo, "sha256").hexdigest()


def validar_zip(ruta: Path) -> None:
    """Comprueba que el archivo sea un ZIP completo y sin daños."""
    if not zipfile.is_zipfile(ruta):
        raise ArchivoInvalido("no es un archivo ZIP")
    with zipfile.ZipFile(ruta) as comprimido:
        danado = comprimido.testzip()
    if danado:
        raise ArchivoInvalido(f"el ZIP tiene un archivo dañado: {danado}")


def validar_xlsx(ruta: Path) -> None:
    """Comprueba que el archivo sea un libro de Excel."""
    validar_zip(ruta)
    with zipfile.ZipFile(ruta) as libro:
        if "xl/workbook.xml" not in libro.namelist():
            raise ArchivoInvalido("el ZIP no es un libro de Excel")


# Función que valida cada formato. Un formato nuevo necesita su función aquí.
VALIDADORES = {
    "xlsx": validar_xlsx,
    "zip": validar_zip,
}


def validar(ruta: Path, formato: str) -> None:
    """Comprueba que el archivo no esté vacío y tenga el formato esperado."""
    if ruta.stat().st_size == 0:
        raise ArchivoInvalido("el archivo está vacío")
    VALIDADORES[formato](ruta)


def bajar(url: str, destino: Path) -> None:
    """Guarda en destino el contenido de la URL. Reintenta si falla la conexión."""
    for intento in range(1, INTENTOS + 1):
        try:
            with requests.get(
                url, headers=ENCABEZADOS, stream=True, timeout=TIEMPO_LIMITE
            ) as respuesta:
                respuesta.raise_for_status()
                with destino.open("wb") as archivo:
                    for bloque in respuesta.iter_content(TAMANO_BLOQUE):
                        archivo.write(bloque)
            return
        except requests.RequestException as error:
            if intento == INTENTOS:
                raise
            espera = ESPERA_REINTENTO * 2 ** (intento - 1)
            print(f"  Intento {intento} de {INTENTOS} falló: {error}")
            print(f"  Nuevo intento en {espera} s.")
            time.sleep(espera)


def leer_registro() -> list[dict[str, str]]:
    """Lee las descargas registradas en catalog/ingestions.csv."""
    with REGISTRO.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def ultimo_registro(ruta: Path) -> dict[str, str] | None:
    """Devuelve la última fila registrada del archivo, o None si no tiene."""
    filas = [f for f in leer_registro() if f["raw_path"] == ruta_relativa(ruta)]
    return filas[-1] if filas else None


def registrar(fuente: Fuente, ruta: Path, checksum: str) -> None:
    """Agrega la descarga a catalog/ingestions.csv."""
    fecha = datetime.now().astimezone()
    fila = {
        "ingestion_id": f"{fuente.dataset_id}_{fecha:%Y%m%dT%H%M%S}",
        "dataset_id": fuente.dataset_id,
        "retrieved_at": fecha.isoformat(timespec="seconds"),
        "raw_path": ruta_relativa(ruta),
        "checksum": checksum,
        "status": "ok",
        "notes": "",
        "download_url": fuente.url,
    }
    with REGISTRO.open(newline="", encoding="utf-8") as archivo:
        columnas = next(csv.reader(archivo))
    with REGISTRO.open("a", newline="", encoding="utf-8") as archivo:
        csv.DictWriter(archivo, columnas, lineterminator="\n").writerow(fila)


def revisar_existente(ruta: Path) -> None:
    """Compara la huella de un archivo que ya existe con la de su último registro."""
    registro = ultimo_registro(ruta)
    actual = huella(ruta)
    if registro is None:
        print("  Ya existe y no está en el registro; no se descarga de nuevo.")
        print(f"  Huella: {actual}")
    elif registro["checksum"] == actual:
        print("  Ya existe y su huella coincide con el registro; no se descarga.")
    else:
        fecha = registro["retrieved_at"]
        raise ArchivoInvalido(
            f"ya existe, pero su huella no es la registrada el {fecha}"
        )


def descargar(fuente: Fuente) -> bool:
    """Descarga la fuente a data/raw, la valida y la registra.

    Nunca sobrescribe: si el archivo ya existe, solo compara su huella con la del
    registro. Si lo descargado es idéntico a la última descarga registrada, no
    agrega otra fila. Devuelve True si agregó una fila.
    """
    ruta = RAW_DATA_DIR / fuente.archivo
    if ruta.exists():
        revisar_existente(ruta)
        return False

    parcial = ruta.with_name(ruta.name + ".part")
    try:
        bajar(fuente.url, parcial)
        validar(parcial, fuente.formato)
        parcial.rename(ruta)
    finally:
        parcial.unlink(missing_ok=True)
    print(f"  Descargado: {ruta_relativa(ruta)} ({ruta.stat().st_size:,} bytes)")

    actual = huella(ruta)
    registro = ultimo_registro(ruta)
    if registro and registro["checksum"] == actual:
        fecha = registro["retrieved_at"]
        print(f"  Coincide con la descarga registrada el {fecha}; no se agrega fila.")
        return False

    registrar(fuente, ruta, actual)
    return True


def escribir_descripcion() -> None:
    """Describe la última descarga de cada fuente en un archivo de texto."""
    ultimas = {fila["raw_path"]: fila for fila in leer_registro()}
    lineas = [
        "# Fuentes descargadas",
        "",
        "Archivo generado por `health_data.ingestion.descarga` a partir de "
        "`catalog/ingestions.csv`. No editar a mano.",
    ]
    for fuente in FUENTES:
        fila = ultimas.get(ruta_relativa(RAW_DATA_DIR / fuente.archivo))
        if fila is None:
            continue
        fecha = datetime.fromisoformat(fila["retrieved_at"])
        lineas += [
            "",
            f"## {fuente.dataset_id}: {fuente.nombre}",
            "",
            fuente.descripcion,
            "",
            f"- Fuente: {fuente.institucion}",
            f"- Descarga: {fuente.url}",
            f"- Fecha de descarga: {fecha:%d/%m/%Y %H:%M}",
            f"- Archivo crudo: `{fila['raw_path']}`",
            f"- SHA-256: `{fila['checksum'].removeprefix('sha256:')}`",
        ]
        if fuente.nota:
            lineas += ["", fuente.nota]
    DESCRIPCION.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> None:
    """Descarga la fuente indicada y actualiza la descripción de las fuentes."""
    fuentes = {fuente.dataset_id: fuente for fuente in FUENTES}
    parser = argparse.ArgumentParser(description="Descarga una fuente a data/raw.")
    parser.add_argument("dataset_id", choices=fuentes, help="por ejemplo, SALUD-001")
    fuente = fuentes[parser.parse_args().dataset_id]

    ensure_directories()
    print(f"{fuente.dataset_id}: {fuente.archivo}")
    try:
        registrada = descargar(fuente)
    except (requests.RequestException, ArchivoInvalido) as error:
        raise SystemExit(f"  Error: {error}")

    if registrada:
        escribir_descripcion()
        print(f"Descripción de las fuentes: {ruta_relativa(DESCRIPCION)}")


if __name__ == "__main__":
    main()
