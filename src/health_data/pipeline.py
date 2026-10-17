"""Pipeline principal y orquestador de Data Health MCD Unison.

Coordina la descarga, limpieza, validación y consolidación de datos de salud
y accesibilidad carretera en Sonora.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from health_data.config import (
    ARCHIVO_MANIFIESTO,
    ARCHIVO_TABLA_FINAL,
    DIR_CONFIG,
    INTERIM_DATA_DIR,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    cargar_configuracion,
    ensure_directories,
)
from health_data.ingestion.descarga import descargar_dataset
from health_data.processing import cartografia

log = logging.getLogger("health_data.pipeline")
ARCHIVO_INGESTAS = DIR_CONFIG.parent / "catalog" / "ingestions.csv"
COLUMNAS_INGESTAS = [
    "ingestion_id",
    "dataset_id",
    "retrieved_at",
    "raw_path",
    "checksum",
    "status",
    "notes",
]

# Re-exportaciones compatibles con versiones anteriores
__all__ = [
    "PROJECT_ROOT",
    "RAW_DATA_DIR",
    "INTERIM_DATA_DIR",
    "PROCESSED_DATA_DIR",
    "ensure_directories",
    "run_pipeline",
]


def paso_cartografia(*, forzar: bool = False) -> None:
    """Descarga y asegura la cartografía vectorial de Sonora."""
    log.info("=== Paso: Cartografía de Sonora ===")
    capas = cartografia.asegurar_cartografia(forzar=forzar)
    for nombre, ruta in capas.items():
        if ruta:
            log.info("  Capa lista: %s (%s)", nombre, ruta.name)
        else:
            log.warning("  No se pudo obtener la capa: %s", nombre)


def paso_descargas(*, forzar: bool = False) -> dict[str, object]:
    """Descarga las fuentes aprobadas registradas en la configuración."""
    log.info("=== Paso: Descarga de fuentes ===")
    cfg = cargar_configuracion()
    resultados = {}

    for dataset_id, fuente in cfg.fuentes.items():
        if fuente.estado == "approved" and fuente.url and fuente.nombre_archivo:
            try:
                res = descargar_dataset(
                    dataset_id=dataset_id,
                    url=fuente.url,
                    nombre_archivo=fuente.nombre_archivo,
                    forzar=forzar,
                )
                registrar_ingesta(
                    dataset_id,
                    res.ruta,
                    "reused" if res.reutilizado else "downloaded",
                    f"{res.bytes_descargados} bytes",
                )
                resultados[dataset_id] = {
                    "bytes": res.bytes_descargados,
                    "reutilizado": res.reutilizado,
                    "ruta": str(res.ruta),
                }
            except Exception as exc:
                registrar_ingesta(dataset_id, None, "failed", str(exc))
                log.error("[%s] No se pudo descargar: %s", dataset_id, exc)
                resultados[dataset_id] = {"error": str(exc)}

    return resultados


def registrar_ingesta(
    dataset_id: str,
    ruta: Path | None,
    estado: str,
    notas: str,
) -> None:
    """Anexa al catálogo el resultado y checksum de una ingesta."""
    ARCHIVO_INGESTAS.parent.mkdir(parents=True, exist_ok=True)
    existe = ARCHIVO_INGESTAS.exists() and ARCHIVO_INGESTAS.stat().st_size > 0
    checksum = ""
    ruta_relativa = ""
    if ruta is not None:
        digest = hashlib.sha256()
        with ruta.open("rb") as archivo:
            for bloque in iter(lambda: archivo.read(1 << 20), b""):
                digest.update(bloque)
        checksum = digest.hexdigest()
        ruta_relativa = ruta.relative_to(PROJECT_ROOT).as_posix()
    fila = {
        "ingestion_id": datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"),
        "dataset_id": dataset_id,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "raw_path": ruta_relativa,
        "checksum": checksum,
        "status": estado,
        "notes": notas.replace("\n", " "),
    }
    with ARCHIVO_INGESTAS.open("a", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS_INGESTAS)
        if not existe:
            escritor.writeheader()
        escritor.writerow(fila)


def guardar_manifiesto(
    segundos: float,
    descargas: dict[str, object],
    args: dict[str, object],
    *,
    estado: str = "success",
    error: str | None = None,
) -> Path:
    """Genera el manifiesto de trazabilidad de la ejecución del pipeline."""
    tabla_final: dict[str, object] | None = None
    if ARCHIVO_TABLA_FINAL.exists():
        digest = hashlib.sha256()
        with ARCHIVO_TABLA_FINAL.open("rb") as archivo:
            for bloque in iter(lambda: archivo.read(1 << 20), b""):
                digest.update(bloque)
        tabla_final = {
            "ruta": ARCHIVO_TABLA_FINAL.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": ARCHIVO_TABLA_FINAL.stat().st_size,
            "sha256": digest.hexdigest(),
        }
    manifiesto = {
        "proyecto": "Data Health MCD Unison",
        "generado_en": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "duracion_segundos": round(segundos, 2),
        "estado": estado,
        "error": error,
        "entorno": {
            "python": sys.version,
            "plataforma": platform.platform(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "argumentos": args,
        "descargas": descargas,
        "archivos_salida": {"tabla_final": tabla_final},
    }

    ARCHIVO_MANIFIESTO.parent.mkdir(parents=True, exist_ok=True)
    with ARCHIVO_MANIFIESTO.open("w", encoding="utf-8") as fh:
        json.dump(manifiesto, fh, ensure_ascii=False, indent=2, default=str)

    log.info("Manifiesto generado en: %s", ARCHIVO_MANIFIESTO)
    return ARCHIVO_MANIFIESTO


def run_pipeline(
    *,
    forzar: bool = False,
    solo_descarga: bool = False,
    metodo_ruteo: str = "estimated",
) -> None:
    """Ejecuta las etapas principales del pipeline de datos."""
    if metodo_ruteo not in {"estimated", "sakbe"}:
        raise ValueError("El método debe ser 'estimated' o 'sakbe'.")
    inicio = time.monotonic()
    ensure_directories()
    descargas: dict[str, object] = {}
    argumentos = {
        "forzar": forzar,
        "solo_descarga": solo_descarga,
        "metodo_ruteo": metodo_ruteo,
    }

    try:
        print("Data Health MCD Unison")
        print(f"Directorio raíz: {PROJECT_ROOT}")
        print(f"Datos crudos: {RAW_DATA_DIR}")
        print(f"Datos intermedios: {INTERIM_DATA_DIR}")
        print(f"Datos procesados: {PROCESSED_DATA_DIR}")

        paso_cartografia(forzar=forzar)
        descargas = paso_descargas(forzar=forzar)
        if solo_descarga:
            print("Etapa de descarga terminada.")
            guardar_manifiesto(
                time.monotonic() - inicio,
                descargas,
                argumentos,
                estado="success",
            )
            return

        requeridos = {
            "CONEVAL-ACC-001": RAW_DATA_DIR / "coneval_gacp2020_localidades.zip",
            "INEGI-POP-001": RAW_DATA_DIR / "iter_26csv20.zip",
            "SALUD-001": RAW_DATA_DIR / "ESTABLECIMIENTO_SALUD_202608.xlsx",
        }
        faltantes = [str(ruta) for ruta in requeridos.values() if not ruta.exists()]
        if faltantes:
            raise FileNotFoundError(
                "Faltan fuentes crudas requeridas para procesar: "
                + ", ".join(faltantes)
            )

        archivos_procesados = (
            (
                RAW_DATA_DIR / "coneval_gacp2020_localidades.zip",
                PROCESSED_DATA_DIR / "coneval-acc-001_localidades.parquet",
                "health_data.processing.coneval_acc_001",
                "CONEVAL-ACC-001",
            ),
            (
                RAW_DATA_DIR / "iter_26csv20.zip",
                PROCESSED_DATA_DIR / "inegi-pop-001_localidades.parquet",
                "health_data.processing.inegi_pop_001",
                "INEGI-POP-001",
            ),
            (
                RAW_DATA_DIR / "ESTABLECIMIENTO_SALUD_202608.xlsx",
                PROCESSED_DATA_DIR / "salud-001_establecimientos.parquet",
                "health_data.processing.salud_001",
                "SALUD-001",
            ),
        )
        for crudo, procesado, modulo, dataset_id in archivos_procesados:
            if forzar or not procesado.exists():
                log.info("Procesando %s...", dataset_id)
                mod = __import__(modulo, fromlist=["main"])
                mod.main()

        from health_data.processing.ruteo import consolidar_dataset_final

        metodo_actual = None
        if ARCHIVO_TABLA_FINAL.exists():
            tabla_existente = pd.read_parquet(ARCHIVO_TABLA_FINAL)
            if "routing_method" in tabla_existente and not tabla_existente.empty:
                metodos = tabla_existente["routing_method"].dropna().unique()
                metodo_actual = metodos[0] if len(metodos) == 1 else None
        if (
            forzar
            or not ARCHIVO_TABLA_FINAL.exists()
            or metodo_actual != metodo_ruteo
            or metodo_ruteo == "sakbe"
        ):
            consolidar_dataset_final(metodo=metodo_ruteo)

        from health_data.validacion import validar_archivo_procesado

        reporte = validar_archivo_procesado()
        if not reporte.paso:
            fallas = "; ".join(
                f"{comp.nombre}: {comp.detalle}" for comp in reporte.fallidas
            )
            raise RuntimeError(f"Falló la validación del dataset final: {fallas}")

        print(f"Pipeline ejecutado en {time.monotonic() - inicio:.2f} s.")
    except Exception as exc:
        guardar_manifiesto(
            time.monotonic() - inicio,
            descargas,
            argumentos,
            estado="failed",
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
    else:
        guardar_manifiesto(
            time.monotonic() - inicio,
            descargas,
            argumentos,
            estado="success",
        )


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de CLI para el pipeline."""
    parser = argparse.ArgumentParser(
        prog="python -m health_data.pipeline",
        description="Pipeline de datos para accesibilidad en salud en Sonora.",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Fuerza la descarga y reprocesamiento aunque existan cachés.",
    )
    parser.add_argument(
        "--solo-cartografia",
        action="store_true",
        help="Solo descarga y verifica el GeoJSON de los 72 municipios de Sonora.",
    )
    parser.add_argument(
        "--solo-descarga",
        action="store_true",
        help="Descarga las fuentes y termina.",
    )
    parser.add_argument(
        "--ruteo",
        choices=("estimated", "sakbe"),
        default="estimated",
        help="Método: estimación exploratoria o API SAKBÉ (requiere SAKBE_TOKEN).",
    )
    parser.add_argument(
        "--verboso",
        action="store_true",
        help="Activa registro detallado en consola.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verboso else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.solo_cartografia:
        paso_cartografia(forzar=args.forzar)
        return 0

    run_pipeline(
        forzar=args.forzar,
        solo_descarga=args.solo_descarga,
        metodo_ruteo=args.ruteo,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())