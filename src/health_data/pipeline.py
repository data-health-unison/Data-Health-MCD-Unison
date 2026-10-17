"""Pipeline principal y orquestador de Data Health MCD Unison.

Coordina la descarga, limpieza, validación y consolidación de datos de salud
y accesibilidad carretera en Sonora.
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from health_data.config import (
    ARCHIVO_MANIFIESTO,
    ARCHIVO_TABLA_FINAL,
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
                resultados[dataset_id] = {
                    "bytes": res.bytes_descargados,
                    "reutilizado": res.reutilizado,
                    "ruta": str(res.ruta),
                }
            except Exception as exc:
                log.warning("[%s] No se pudo descargar: %s", dataset_id, exc)
                resultados[dataset_id] = {"error": str(exc)}

    return resultados


def guardar_manifiesto(
    segundos: float, descargas: dict[str, object], args: dict[str, object]
) -> Path:
    """Genera el manifiesto de trazabilidad de la ejecución del pipeline."""
    manifiesto = {
        "proyecto": "Data Health MCD Unison",
        "generado_en": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "duracion_segundos": round(segundos, 2),
        "entorno": {
            "python": sys.version,
            "plataforma": platform.platform(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "argumentos": args,
        "descargas": descargas,
        "archivos_salida": {
            "tabla_final": str(ARCHIVO_TABLA_FINAL.relative_to(PROJECT_ROOT))
            if ARCHIVO_TABLA_FINAL.exists()
            else None,
        },
    }

    ARCHIVO_MANIFIESTO.parent.mkdir(parents=True, exist_ok=True)
    with ARCHIVO_MANIFIESTO.open("w", encoding="utf-8") as fh:
        json.dump(manifiesto, fh, ensure_ascii=False, indent=2, default=str)

    log.info("Manifiesto generado en: %s", ARCHIVO_MANIFIESTO)
    return ARCHIVO_MANIFIESTO


def run_pipeline(*, forzar: bool = False, solo_descarga: bool = False) -> None:
    """Ejecuta las etapas principales del pipeline de datos."""
    inicio = time.monotonic()
    ensure_directories()

    print("Data Health MCD Unison")
    print(f"Directorio raíz: {PROJECT_ROOT}")
    print(f"Datos crudos: {RAW_DATA_DIR}")
    print(f"Datos intermedios: {INTERIM_DATA_DIR}")
    print(f"Datos procesados: {PROCESSED_DATA_DIR}")

    # 1. Cartografía
    paso_cartografia(forzar=forzar)

    # 2. Descargas
    descargas = paso_descargas(forzar=forzar)
    if solo_descarga:
        print("Etapa de descarga terminada.")
        return

    # 3. Procesamientos individuales
    print("Verificando módulos de procesamiento...")

    # 3.1 CONEVAL-ACC-001
    coneval_crudo = RAW_DATA_DIR / "coneval_gacp2020_localidades.zip"
    archivo_coneval_proc = PROCESSED_DATA_DIR / "coneval-acc-001_localidades.parquet"
    if coneval_crudo.exists() and (forzar or not archivo_coneval_proc.exists()):
        try:
            from health_data.processing.coneval_acc_001 import main as proc_coneval
            print("Ejecutando procesamiento de CONEVAL-ACC-001...")
            proc_coneval()
        except Exception as exc:
            log.warning("No se pudo ejecutar coneval_acc_001: %s", exc)

    # 3.2 INEGI-POP-001 (ITER)
    iter_crudo = RAW_DATA_DIR / "iter_26csv20.zip"
    archivo_iter_proc = PROCESSED_DATA_DIR / "inegi-pop-001_localidades.parquet"
    if iter_crudo.exists() and (forzar or not archivo_iter_proc.exists()):
        try:
            from health_data.processing.inegi_pop_001 import main as proc_iter
            print("Ejecutando procesamiento de INEGI-POP-001 (ITER)...")
            proc_iter()
        except Exception as exc:
            log.warning("No se pudo ejecutar inegi_pop_001: %s", exc)

    # 3.3 SALUD-001 (CLUES)
    clues_crudo = RAW_DATA_DIR / "ESTABLECIMIENTO_SALUD_202608.xlsx"
    archivo_salud_proc = PROCESSED_DATA_DIR / "salud-001_establecimientos.parquet"
    if clues_crudo.exists() and (forzar or not archivo_salud_proc.exists()):
        try:
            from health_data.processing.salud_001 import main as proc_salud
            print("Ejecutando procesamiento de SALUD-001 (CLUES)...")
            proc_salud()
        except Exception as exc:
            log.warning("No se pudo ejecutar salud_001: %s", exc)

    # 3.4 Ruteo y Accesibilidad a Centros de Salud
    if archivo_iter_proc.exists() and archivo_salud_proc.exists() and (forzar or not ARCHIVO_TABLA_FINAL.exists()):
        try:
            from health_data.processing.ruteo import main as proc_ruteo
            print("Ejecutando cálculo de ruteo de salud...")
            proc_ruteo()
        except Exception as exc:
            log.warning("No se pudo ejecutar ruteo: %s", exc)

    # 3.5 Validación de calidad
    if ARCHIVO_TABLA_FINAL.exists():
        try:
            from health_data.validacion import ejecutar_todas
            print("Ejecutando validación de calidad del dataset final...")
            reporte = ejecutar_todas()
            if not reporte.todas_pasan:
                log.warning("Advertencia: Se detectaron inconsistencias en la validación.")
        except Exception as exc:
            log.warning("No se pudo ejecutar validacion: %s", exc)

    # 4. Guardar manifiesto de ejecución
    segundos = time.monotonic() - inicio
    guardar_manifiesto(segundos, descargas, {"forzar": forzar})
    print(f"Pipeline ejecutado en {segundos:.2f} s.")


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

    run_pipeline(forzar=args.forzar, solo_descarga=args.solo_descarga)
    return 0


if __name__ == "__main__":
    sys.exit(main())