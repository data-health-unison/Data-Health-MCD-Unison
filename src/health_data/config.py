"""Configuración central del proyecto Data Health MCD Unison.

Rutas, fuentes y umbrales metodológicos de accesibilidad a servicios de salud.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# --------------------------------------------------------------------------
# Rutas del proyecto
# --------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIR_CONFIG = PROJECT_ROOT / "config"
DIR_DATOS = PROJECT_ROOT / "data"

RAW_DATA_DIR = DIR_DATOS / "raw"
INTERIM_DATA_DIR = DIR_DATOS / "interim"
PROCESSED_DATA_DIR = DIR_DATOS / "processed"

# Alias compatibles con enigh-sonora
DIR_RAW = RAW_DATA_DIR
DIR_INTERIM = INTERIM_DATA_DIR
DIR_PROCESSED = PROCESSED_DATA_DIR
DIR_GEO = PROCESSED_DATA_DIR / "geografia"

ARCHIVO_FUENTES = DIR_CONFIG / "fuentes_health.yaml"
ARCHIVO_MANIFIESTO = PROCESSED_DATA_DIR / "manifiesto.json"
ARCHIVO_TABLA_FINAL = PROCESSED_DATA_DIR / "accesibilidad_localidades.parquet"

# Claves geográficas de la entidad de interés
CLAVE_SONORA = "26"
NOMBRE_SONORA = "Sonora"


# --------------------------------------------------------------------------
# Modelo de configuración
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Umbrales:
    """Umbrales analíticos y de calidad para accesibilidad a salud."""

    tiempo_critico_min: int = 60
    tiempo_muy_critico_min: int = 120
    tiempo_critico_segundo_nivel_min: int = 120
    poblacion_min_localidad: int = 100
    sakbe_limite_diario: int = 2500
    cv_no_fiable: float = 0.25


@dataclass(frozen=True)
class FuenteInfo:
    """Metadatos de una fuente de datos."""

    dataset_id: str
    nombre: str
    url: str = ""
    api_base: str = ""
    token_env: str = ""
    nombre_archivo: str = ""
    estado: str = "approved"
    prioridad: str = "alta"
    limite_diario: int | None = None


@dataclass(frozen=True)
class Configuracion:
    """Configuración validada del proyecto."""

    fuentes: dict[str, FuenteInfo]
    umbrales: Umbrales = field(default_factory=Umbrales)

    def fuente(self, dataset_id: str) -> FuenteInfo:
        """Devuelve la información de una fuente o lanza KeyError descriptivo."""
        if dataset_id not in self.fuentes:
            disponibles = ", ".join(sorted(self.fuentes))
            raise KeyError(
                f"La fuente '{dataset_id}' no está en config/fuentes_health.yaml. "
                f"Fuentes disponibles: {disponibles}"
            )
        return self.fuentes[dataset_id]


# --------------------------------------------------------------------------
# Funciones de carga y entorno
# --------------------------------------------------------------------------


def ensure_directories() -> None:
    """Crea la estructura de directorios de datos si no existe."""
    for directorio in (RAW_DATA_DIR, INTERIM_DATA_DIR, PROCESSED_DATA_DIR, DIR_GEO):
        directorio.mkdir(parents=True, exist_ok=True)


asegurar_directorios = ensure_directories


@functools.lru_cache(maxsize=1)
def cargar_configuracion(ruta: Path | None = None) -> Configuracion:
    """Carga y valida la configuración del proyecto (cacheada)."""
    archivo = ruta or ARCHIVO_FUENTES
    if not archivo.exists():
        # Configuración por omisión si el archivo aún no existe
        return Configuracion(fuentes={}, umbrales=Umbrales())

    with archivo.open(encoding="utf-8") as fh:
        datos: dict[str, Any] = yaml.safe_load(fh) or {}

    umbrales_brutos = datos.get("umbrales") or {}
    umbrales = Umbrales(
        **{
            k: v
            for k, v in umbrales_brutos.items()
            if k in Umbrales.__dataclass_fields__
        }
    )

    fuentes: dict[str, FuenteInfo] = {}
    for dataset_id, f in (datos.get("fuentes") or {}).items():
        fuentes[str(dataset_id)] = FuenteInfo(
            dataset_id=str(f.get("dataset_id", dataset_id)),
            nombre=str(f.get("nombre", dataset_id)),
            url=str(f.get("url", "")),
            api_base=str(f.get("api_base", "")),
            token_env=str(f.get("token_env", "")),
            nombre_archivo=str(f.get("nombre_archivo", "")),
            estado=str(f.get("estado", "approved")),
            prioridad=str(f.get("prioridad", "alta")),
            limite_diario=f.get("limite_diario"),
        )

    return Configuracion(fuentes=fuentes, umbrales=umbrales)
