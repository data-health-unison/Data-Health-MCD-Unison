"""Respaldo y restauración del caché de SAKBÉ (data/interim/sakbe_cache.sqlite).

El caché guarda las respuestas de la API de Ruteo; regenerarlo cuesta días de cuota y sin él
nadie más puede reproducir la tabla final. No contiene los tokens, solo una huella corta de cada uno.

- ``make respaldo-sakbe`` crea una copia comprimida en data/respaldos/ y la registra en
  catalog/respaldos.csv. La copia se sube a mano a la carpeta compartida del equipo.
- ``make restaurar-sakbe ARCHIVO=...`` revisa que el archivo descargado sea un respaldo registrado
  e intacto, y lo coloca en data/interim/. No reemplaza un caché distinto sin ``--forzar``, y aun
  así guarda una copia del anterior.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from health_data.config import PROJECT_ROOT
from health_data.ingestion.sakbe import ARCHIVO_CACHE, resumen_cache
from health_data.trazabilidad import huella, ruta_relativa

DIR_RESPALDOS = PROJECT_ROOT / "data" / "respaldos"
REGISTRO_RESPALDOS = PROJECT_ROOT / "catalog" / "respaldos.csv"
COLUMNAS_RESPALDOS = [
    "id_respaldo",
    "fecha_respaldo",
    "archivo",
    "huella_archivo",
    "huella_contenido",
    "respuestas",
    "exitosas",
    "primera_consulta",
    "ultima_consulta",
    "notas",
]


class ErrorDeRespaldo(RuntimeError):
    """El respaldo no se pudo crear o restaurar sin riesgo."""


def leer_respaldos(registro: Path | None = None) -> list[dict[str, str]]:
    """Respaldos registrados en catalog/respaldos.csv."""
    registro = registro or REGISTRO_RESPALDOS
    if not registro.exists():
        return []
    with registro.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def _registrar(fila: dict[str, str], registro: Path) -> None:
    nuevo = not registro.exists()
    registro.parent.mkdir(parents=True, exist_ok=True)
    with registro.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, COLUMNAS_RESPALDOS, lineterminator="\n")
        if nuevo:
            escritor.writeheader()
        escritor.writerow(fila)


def respaldar(
    origen: Path | None = None,
    destino_dir: Path | None = None,
    registro: Path | None = None,
) -> Path | None:
    """Comprime una copia del caché y la registra; None si es igual al último respaldo."""
    origen = origen or ARCHIVO_CACHE
    destino_dir = destino_dir or DIR_RESPALDOS
    registro = registro or REGISTRO_RESPALDOS
    if not origen.exists():
        raise ErrorDeRespaldo(f"No existe el caché {origen}.")

    destino_dir.mkdir(parents=True, exist_ok=True)
    fecha = datetime.now().astimezone()
    copia = destino_dir / f".sakbe_cache_{fecha:%Y%m%dT%H%M%S}.sqlite"
    # La API de respaldo de SQLite da una copia consistente aunque el caché esté abierto
    with sqlite3.connect(f"file:{origen.resolve().as_posix()}?mode=ro", uri=True) as fuente, \
            sqlite3.connect(copia) as destino:
        fuente.backup(destino)
    try:
        resumen = resumen_cache(copia)
        anteriores = leer_respaldos(registro)
        if anteriores and anteriores[-1]["huella_contenido"] == resumen["huella_contenido"]:
            print(
                f"El caché es igual al último respaldo ({anteriores[-1]['archivo']}, "
                f"{anteriores[-1]['fecha_respaldo']}); no hace falta otro."
            )
            return None
        comprimido = destino_dir / f"sakbe_cache_{fecha:%Y%m%dT%H%M%S}.sqlite.gz"
        with copia.open("rb") as entrada, gzip.open(comprimido, "wb") as salida:
            shutil.copyfileobj(entrada, salida)
    finally:
        copia.unlink(missing_ok=True)

    _registrar(
        {
            "id_respaldo": f"SAKBE_{fecha:%Y%m%dT%H%M%S}",
            "fecha_respaldo": fecha.isoformat(timespec="seconds"),
            "archivo": comprimido.name,
            "huella_archivo": huella(comprimido),
            "huella_contenido": resumen["huella_contenido"],
            "respuestas": str(resumen["respuestas"]),
            "exitosas": str(resumen["exitosas"]),
            "primera_consulta": resumen["primera_consulta"] or "",
            "ultima_consulta": resumen["ultima_consulta"] or "",
            "notas": "",
        },
        registro,
    )
    return comprimido


def restaurar(
    archivo: Path,
    destino: Path | None = None,
    registro: Path | None = None,
    *,
    forzar: bool = False,
) -> Path:
    """Coloca un respaldo registrado como caché, después de verificar que esté intacto."""
    destino = destino or ARCHIVO_CACHE
    registro = registro or REGISTRO_RESPALDOS
    if not archivo.exists():
        raise ErrorDeRespaldo(f"No existe el archivo {archivo}.")

    actual = huella(archivo)
    fila = next((f for f in leer_respaldos(registro) if f["huella_archivo"] == actual), None)
    if fila is None:
        raise ErrorDeRespaldo(
            f"{archivo.name} no coincide con ningún respaldo de {registro.name}. "
            "Puede estar incompleto o ser de otra versión; vuelva a descargarlo."
        )

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".restaurando")
    try:
        with gzip.open(archivo, "rb") as entrada, temporal.open("wb") as salida:
            shutil.copyfileobj(entrada, salida)
        resumen = resumen_cache(temporal)
        if resumen["huella_contenido"] != fila["huella_contenido"]:
            raise ErrorDeRespaldo(f"El contenido de {archivo.name} no es el registrado.")

        if destino.exists():
            existente = resumen_cache(destino)
            if existente["huella_contenido"] == fila["huella_contenido"]:
                print(f"{ruta_relativa(destino)} ya tiene este respaldo; no se cambió nada.")
                return destino
            if not forzar:
                raise ErrorDeRespaldo(
                    f"Ya existe {ruta_relativa(destino)} con {existente['respuestas']:,} respuestas, distinto "
                    "del respaldo. Use --forzar para reemplazarlo (se guarda una copia del actual)."
                )
            anterior = destino.with_name(f"{destino.stem}.anterior-{datetime.now():%Y%m%dT%H%M%S}{destino.suffix}")
            destino.rename(anterior)
            print(f"El caché anterior quedó en {ruta_relativa(anterior)}.")
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)
    return destino


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m health_data.ingestion.respaldo_sakbe",
        description="Respalda o restaura el caché de SAKBÉ.",
    )
    sub = parser.add_subparsers(dest="accion", required=True)
    sub.add_parser("respaldar", help="Crea una copia comprimida en data/respaldos/ y la registra.")
    rest = sub.add_parser("restaurar", help="Coloca un respaldo descargado en data/interim/.")
    rest.add_argument("archivo", type=Path, help="Ruta del .sqlite.gz descargado.")
    rest.add_argument("--forzar", action="store_true", help="Reemplaza un caché distinto (guarda una copia).")
    args = parser.parse_args(argv)

    try:
        if args.accion == "respaldar":
            comprimido = respaldar()
            if comprimido is not None:
                fila = leer_respaldos()[-1]
                print(f"Respaldo: {ruta_relativa(comprimido)} ({comprimido.stat().st_size / 1e6:.1f} MB)")
                print(f"  Respuestas: {int(fila['respuestas']):,} ({int(fila['exitosas']):,} con ruta)")
                print(f"  Consultas del {fila['primera_consulta']} al {fila['ultima_consulta']}")
                print(f"  Huella: {fila['huella_archivo']}")
                print(f"Registrado en {ruta_relativa(REGISTRO_RESPALDOS)}.")
                print("Siguiente paso: subir el archivo a la carpeta compartida del equipo y hacer commit del registro.")
        else:
            destino = restaurar(args.archivo, forzar=args.forzar)
            resumen = resumen_cache(destino)
            print(f"Caché listo en {ruta_relativa(destino)}: {resumen['respuestas']:,} respuestas.")
    except ErrorDeRespaldo as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
