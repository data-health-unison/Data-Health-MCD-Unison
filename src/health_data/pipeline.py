"""Pipeline principal y orquestador de Data Health MCD Unison.

Coordina la descarga, limpieza, validación y consolidación de datos de salud
y accesibilidad carretera en Sonora.

Cada corrida deja un manifiesto en data/processed/manifiesto.json (el último, que lee el tablero)
y una copia en data/processed/manifiestos/. El manifiesto dice con qué código se corrió (versión,
commit y cambios sin commit), qué entradas usó (huella de cada crudo y del caché de SAKBÉ), qué pasó
en cada paso, qué archivos quedaron en data/processed (huella, filas y con qué commit se generó
cada uno) y el resultado de la validación.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import logging
import platform
import re
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from health_data import __version__
from health_data.config import (
    ARCHIVO_MANIFIESTO,
    ARCHIVO_TABLA_FINAL,
    INTERIM_DATA_DIR,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    ensure_directories,
)
from health_data.ingestion.descarga import descargar_dataset, fuentes_descargables
from health_data.processing import cartografia
from health_data.trazabilidad import describir_archivo, estado_git, ruta_relativa
from health_data.validacion import ReporteValidacion, validar_archivo_procesado

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

# Procesamiento de cada fuente: (id_fuente, módulo). Cada módulo define ARCHIVO_CRUDO, SALIDAS y main().
PROCESAMIENTOS: tuple[tuple[str, str], ...] = (
    ("CONEVAL-ACC-001", "health_data.processing.coneval_acc_001"),
    ("INEGI-POP-001", "health_data.processing.inegi_pop_001"),
    ("SALUD-001", "health_data.processing.salud_001"),
    ("INEGI-GEO-001", "health_data.processing.inegi_geo_001"),
)
# Entradas del ruteo, que deja la tabla final
INSUMOS_RUTEO = ("inegi-pop-001_localidades.parquet", "salud-001_establecimientos.parquet")

ESTADO_EJECUTADO = "ejecutado"
ESTADO_REUTILIZADO = "reutilizado"
ESTADO_OMITIDO = "omitido"
ESTADO_FALLIDO = "fallido"


@dataclass
class Paso:
    """Qué pasó en un paso del pipeline."""

    nombre: str
    estado: str
    segundos: float = 0.0
    detalle: str = ""


def _ejecutar(nombre: str, funcion: Callable[[], Any]) -> Paso:
    """Corre un paso y registra su duración; una excepción lo marca como fallido."""
    inicio = time.monotonic()
    try:
        codigo = funcion()
    except Exception as exc:
        log.warning("[%s] Falló: %s", nombre, exc)
        return Paso(nombre, ESTADO_FALLIDO, round(time.monotonic() - inicio, 2), f"{type(exc).__name__}: {exc}")
    segundos = round(time.monotonic() - inicio, 2)
    if isinstance(codigo, int) and codigo != 0:
        return Paso(nombre, ESTADO_FALLIDO, segundos, f"Terminó con código {codigo}.")
    return Paso(nombre, ESTADO_EJECUTADO, segundos)


def paso_cartografia(*, forzar: bool = False) -> None:
    """Descarga y asegura la cartografía vectorial de Sonora."""
    log.info("=== Paso: Cartografía de Sonora ===")
    capas = cartografia.asegurar_cartografia(forzar=forzar)
    for nombre, ruta in capas.items():
        if ruta:
            log.info("  Capa lista: %s (%s)", nombre, ruta.name)
        else:
            log.warning("  No se pudo obtener la capa: %s", nombre)


def paso_descargas(*, forzar: bool = False) -> dict[str, dict[str, Any]]:
    """Descarga las fuentes aprobadas en catalog/datasets.csv; devuelve un resumen por fuente."""
    log.info("=== Paso: Descarga de fuentes ===")
    resultados: dict[str, dict[str, Any]] = {}

    for dataset_id, fuente in fuentes_descargables().items():
        entrada: dict[str, Any] = {"id_fuente": dataset_id, "edicion": fuente.version}
        try:
            res = descargar_dataset(
                dataset_id=dataset_id,
                url=fuente.url,
                nombre_archivo=fuente.nombre_archivo,
                forzar=forzar,
            )
            entrada |= {
                "ruta": ruta_relativa(res.ruta, PROJECT_ROOT),
                "huella": res.checksum,
                "bytes": res.bytes_descargados,
                "estado": ESTADO_REUTILIZADO if res.reutilizado else "descargado",
                "registrada": res.registrada,
            }
        except Exception as exc:
            log.warning("[%s] No se pudo descargar: %s", dataset_id, exc)
            entrada |= {"estado": ESTADO_FALLIDO, "error": str(exc)}
        resultados[dataset_id] = entrada

    return resultados


def paso_procesamiento(dataset_id: str, nombre_modulo: str, *, forzar: bool = False) -> Paso:
    """Procesa una fuente si su crudo existe y falta alguna salida (o con ``forzar``)."""
    modulo = importlib.import_module(nombre_modulo)
    nombre = f"procesar {dataset_id}"
    if not modulo.ARCHIVO_CRUDO.exists():
        return Paso(nombre, ESTADO_OMITIDO, detalle=f"Falta el crudo {ruta_relativa(modulo.ARCHIVO_CRUDO)}.")
    if not forzar and all(salida.exists() for salida in modulo.SALIDAS):
        return Paso(nombre, ESTADO_REUTILIZADO, detalle="Sus salidas ya existían; `make reprocesar` las regenera.")
    log.info("=== Paso: Procesamiento de %s ===", dataset_id)
    return _ejecutar(nombre, modulo.main)


def paso_ruteo() -> Paso:
    """Recalcula la tabla final usando solo rutas SAKBÉ en caché (no gasta cuota).

    Se ejecuta siempre para incorporar las rutas obtenidas con ``make rutas``.
    """
    log.info("=== Paso: Ruteo a establecimientos de salud ===")

    def correr() -> int:
        from health_data.processing.ruteo import main as proc_ruteo

        print("Ejecutando cálculo de ruteo de salud...")
        return proc_ruteo()

    return _ejecutar("ruteo", correr)


def paso_validacion(ruta: Path | None = None) -> ReporteValidacion | None:
    """Valida la tabla final; devuelve el reporte o None si la tabla no existe."""
    archivo = ruta or ARCHIVO_TABLA_FINAL
    if not archivo.exists():
        log.warning("No existe la tabla final %s; se omite la validación.", archivo)
        return None

    log.info("=== Paso: Validación de calidad ===")
    print("Ejecutando validación de calidad del dataset final...")
    reporte = validar_archivo_procesado(archivo)
    if reporte.paso:
        print(f"Validación: {len(reporte.comprobaciones)} comprobaciones superadas.")
    else:
        log.warning(
            "Validación: %d de %d comprobaciones fallidas (%s).",
            len(reporte.fallidas),
            len(reporte.comprobaciones),
            ", ".join(c.nombre for c in reporte.fallidas),
        )
    return reporte


# --------------------------------------------------------------------------
# Manifiesto
# --------------------------------------------------------------------------


def _paquetes() -> dict[str, str]:
    """Versión instalada de cada dependencia de requirements.txt."""
    requisitos = PROJECT_ROOT / "requirements.txt"
    if not requisitos.exists():
        return {}
    versiones = {}
    for linea in requisitos.read_text(encoding="utf-8").splitlines():
        nombre = re.split(r"[=<>!~\[;\s]", linea.strip(), maxsplit=1)[0]
        if nombre and not nombre.startswith("#"):
            try:
                versiones[nombre] = importlib.metadata.version(nombre)
            except importlib.metadata.PackageNotFoundError:
                versiones[nombre] = None
    return versiones


def _cache_sakbe() -> dict[str, Any] | None:
    """Resumen del caché de SAKBÉ y el respaldo registrado que le corresponde, si hay."""
    from health_data.ingestion.respaldo_sakbe import leer_respaldos
    from health_data.ingestion.sakbe import resumen_cache

    ruta = INTERIM_DATA_DIR / "sakbe_cache.sqlite"
    resumen = resumen_cache(ruta)
    if resumen is None:
        return None
    respaldo = next(
        (r["archivo"] for r in leer_respaldos() if r["huella_contenido"] == resumen["huella_contenido"]), None
    )
    return {"ruta": ruta_relativa(ruta, PROJECT_ROOT), **resumen, "respaldo": respaldo}


def _salidas(commit: str | None) -> list[dict[str, Any]]:
    """Archivos de data/processed (sin los manifiestos), con el commit que generó cada uno."""
    historial = ARCHIVO_MANIFIESTO.parent / "manifiestos"
    archivos = sorted(
        p for p in PROCESSED_DATA_DIR.rglob("*")
        if p.is_file() and p.name != ".gitkeep" and p != ARCHIVO_MANIFIESTO and historial not in p.parents
    )
    salidas = []
    for archivo in archivos:
        descripcion = describir_archivo(archivo, PROJECT_ROOT)
        if "sello" in descripcion:
            sello = descripcion["sello"]
            descripcion["al_dia"] = None if commit is None or sello is None else sello["commit"] == commit
        salidas.append(descripcion)
    return salidas


def _advertencias(manifiesto: dict[str, Any]) -> list[str]:
    """Lo que conviene revisar de una corrida, en frases cortas."""
    avisos = []
    corrida = manifiesto["corrida"]
    if corrida["commit"] is None:
        avisos.append(f"No se registró el commit ({corrida.get('motivo_sin_commit')}).")
    elif corrida["cambios_sin_commit"]:
        avisos.append(
            f"Se corrió con {len(corrida['cambios_sin_commit'])} archivos con cambios sin commit: "
            "el resultado no se puede reproducir solo con el commit."
        )
    for paso in manifiesto["pasos"]:
        if paso["estado"] == ESTADO_FALLIDO:
            avisos.append(f"Falló el paso «{paso['nombre']}»: {paso['detalle']}")
    for entrada in manifiesto["entradas"]["crudos"]:
        if entrada["estado"] == ESTADO_FALLIDO:
            avisos.append(f"No se pudo obtener el crudo de {entrada['id_fuente']}: {entrada.get('error')}")
    cache = manifiesto["entradas"]["cache_sakbe"]
    if cache is not None and cache["respaldo"] is None:
        avisos.append("El caché de SAKBÉ no tiene un respaldo registrado igual; corra `make respaldo-sakbe`.")
    for salida in manifiesto["salidas"]:
        if "error" in salida:
            avisos.append(f"{salida['ruta']}: {salida['error']}")
        if "sello" not in salida:
            continue
        if salida["sello"] is None:
            avisos.append(f"{salida['ruta']} se generó antes de existir el sello; `make reprocesar` lo regenera.")
        elif salida["al_dia"] is False:
            avisos.append(
                f"{salida['ruta']} se generó con el commit {salida['sello']['commit'][:7]}, no con el actual; "
                "si su código cambió, `make reprocesar` lo regenera."
            )
    validacion = manifiesto["validacion"]
    if validacion is not None and not validacion["paso"]:
        avisos.append(f"La validación tiene {len(validacion['fallidas'])} comprobaciones fallidas.")
    return avisos


def construir_manifiesto(
    *,
    inicio: datetime,
    segundos: float,
    argumentos: dict[str, Any],
    git: dict[str, Any],
    descargas: dict[str, dict[str, Any]],
    pasos: list[Paso],
    validacion: ReporteValidacion | None,
) -> dict[str, Any]:
    """Arma el manifiesto de una corrida del pipeline."""
    manifiesto: dict[str, Any] = {
        "proyecto": "Data Health MCD Unison",
        "id_corrida": f"{inicio:%Y%m%dT%H%M%S}",
        "corrida": {
            "inicio": inicio.isoformat(timespec="seconds"),
            "duracion_segundos": round(segundos, 2),
            "version": __version__,
            "commit": git.get("commit"),
            "rama": git.get("rama"),
            "cambios_sin_commit": git.get("cambios_sin_commit", []),
            "argumentos": argumentos,
            "entorno": {
                "python": platform.python_version(),
                "plataforma": platform.platform(),
                "paquetes": _paquetes(),
            },
        },
        "entradas": {
            "crudos": list(descargas.values()),
            "cache_sakbe": _cache_sakbe(),
        },
        "pasos": [asdict(p) for p in pasos],
        "salidas": _salidas(git.get("commit")),
        "validacion": None
        if validacion is None
        else {
            "paso": validacion.paso,
            "comprobaciones": [
                {"nombre": c.nombre, "paso": c.paso, "detalle": c.detalle} for c in validacion.comprobaciones
            ],
            "fallidas": [{"nombre": c.nombre, "detalle": c.detalle} for c in validacion.fallidas],
        },
    }
    if git.get("commit") is None:
        manifiesto["corrida"]["motivo_sin_commit"] = git.get("motivo")
    manifiesto["advertencias"] = _advertencias(manifiesto)
    return manifiesto


def guardar_manifiesto(manifiesto: dict[str, Any]) -> Path:
    """Guarda el manifiesto como el último (manifiesto.json) y en el historial de corridas."""
    historial = ARCHIVO_MANIFIESTO.parent / "manifiestos" / f"{manifiesto['id_corrida']}.json"
    historial.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(manifiesto, ensure_ascii=False, indent=2, default=str)
    for destino in (ARCHIVO_MANIFIESTO, historial):
        destino.write_text(texto + "\n", encoding="utf-8")
    log.info("Manifiesto guardado en %s y %s", ARCHIVO_MANIFIESTO.name, ruta_relativa(historial, PROJECT_ROOT))
    return historial


def run_pipeline(
    *, forzar: bool = False, solo_descarga: bool = False, reprocesar: bool = False
) -> dict[str, Any] | None:
    """Ejecuta las etapas del pipeline y devuelve el manifiesto de la corrida.

    ``reprocesar`` regenera las salidas de cada fuente con los crudos que ya están; ``forzar``
    además vuelve a descargar los crudos (y puede traer una edición nueva de la fuente).
    """
    inicio = datetime.now().astimezone()
    reloj = time.monotonic()
    ensure_directories()
    git = estado_git(PROJECT_ROOT)

    print("Data Health MCD Unison")
    print(f"Versión {__version__} · commit {(git['commit'] or 'sin registrar')[:7]}")
    print(f"Directorio raíz: {PROJECT_ROOT}")

    pasos: list[Paso] = [_ejecutar("cartografia", lambda: paso_cartografia(forzar=forzar))]

    descargas = paso_descargas(forzar=forzar)
    if solo_descarga:
        print("Etapa de descarga terminada.")
        return None

    for dataset_id, nombre_modulo in PROCESAMIENTOS:
        paso = paso_procesamiento(dataset_id, nombre_modulo, forzar=forzar or reprocesar)
        log.info("[%s] %s. %s", paso.nombre, paso.estado, paso.detalle)
        pasos.append(paso)

    if all((PROCESSED_DATA_DIR / nombre).exists() for nombre in INSUMOS_RUTEO):
        pasos.append(paso_ruteo())
    else:
        pasos.append(Paso("ruteo", ESTADO_OMITIDO, detalle="Faltan ITER o CLUES procesados."))

    reporte = paso_validacion()
    if reporte is None:
        pasos.append(Paso("validacion", ESTADO_OMITIDO, detalle="No existe la tabla final."))
    else:
        pasos.append(
            Paso("validacion", ESTADO_EJECUTADO, detalle=f"{len(reporte.fallidas)} de {len(reporte.comprobaciones)} fallidas.")
        )

    segundos = time.monotonic() - reloj
    manifiesto = construir_manifiesto(
        inicio=inicio,
        segundos=segundos,
        argumentos={"forzar": forzar, "reprocesar": reprocesar},
        git=git,
        descargas=descargas,
        pasos=pasos,
        validacion=reporte,
    )
    guardar_manifiesto(manifiesto)

    print(f"Pipeline ejecutado en {segundos:.2f} s.")
    if manifiesto["advertencias"]:
        print("Para revisar:")
        for aviso in manifiesto["advertencias"]:
            print(f"  - {aviso}")
    return manifiesto


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de CLI para el pipeline."""
    parser = argparse.ArgumentParser(
        prog="python -m health_data.pipeline",
        description="Pipeline de datos para accesibilidad en salud en Sonora.",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Vuelve a descargar los crudos y a procesarlo todo (puede traer una edición nueva de una fuente).",
    )
    parser.add_argument(
        "--reprocesar",
        action="store_true",
        help="Regenera las salidas de cada fuente con los crudos que ya están (no descarga nada).",
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

    run_pipeline(forzar=args.forzar, solo_descarga=args.solo_descarga, reprocesar=args.reprocesar)
    return 0


if __name__ == "__main__":
    sys.exit(main())