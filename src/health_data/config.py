"""Configuración central del proyecto Data Health MCD Unison.

Rutas, fuentes y umbrales metodológicos de accesibilidad a servicios de salud.
"""

from __future__ import annotations

import csv
import functools
import os
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
ARCHIVO_CATALOGO = PROJECT_ROOT / "catalog" / "datasets.csv"
ARCHIVO_MANIFIESTO = PROCESSED_DATA_DIR / "manifiesto.json"
ARCHIVO_TABLA_FINAL = PROCESSED_DATA_DIR / "accesibilidad_localidades.parquet"

# Estados de una fuente en catalog/datasets.csv; solo se descargan las aprobadas
ESTADO_PROPUESTA = "propuesta"
ESTADO_APROBADA = "aprobada"
ESTADO_DIFERIDA = "diferida"
ESTADO_RECHAZADA = "rechazada"
ESTADOS_FUENTE = (ESTADO_PROPUESTA, ESTADO_APROBADA, ESTADO_DIFERIDA, ESTADO_RECHAZADA)

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
    sakbe_limite_diario: int = 10_000
    cv_no_fiable: float = 0.25


@dataclass(frozen=True)
class FuenteInfo:
    """Una fuente del catálogo y, si se descarga, cómo se descarga."""

    dataset_id: str
    nombre: str
    # De catalog/datasets.csv: qué es la fuente y en qué estado está
    estado: str = ESTADO_PROPUESTA
    prioridad: str = ""
    institucion: str = ""
    url_fuente: str = ""
    version: str = ""
    responsable: str = ""
    # De config/fuentes_health.yaml: cómo se descarga
    url: str = ""
    api_base: str = ""
    token_env: str = ""
    nombre_archivo: str = ""
    limite_diario: int | None = None
    # Describen el archivo descargado en references/fuentes_descargadas.md
    descripcion: str = ""
    nota: str = ""

    @property
    def descargable(self) -> bool:
        """Aprobada en el catálogo y con enlace y archivo de descarga."""
        return self.estado == ESTADO_APROBADA and bool(self.url and self.nombre_archivo)


@dataclass(frozen=True)
class Configuracion:
    """Configuración validada del proyecto."""

    fuentes: dict[str, FuenteInfo]
    umbrales: Umbrales = field(default_factory=Umbrales)
    # cvegeo de 9 dígitos → motivo; se quitan antes del ruteo y del análisis
    localidades_excluidas: dict[str, str] = field(default_factory=dict)

    def fuente(self, dataset_id: str) -> FuenteInfo:
        """Devuelve la información de una fuente o lanza KeyError descriptivo."""
        if dataset_id not in self.fuentes:
            disponibles = ", ".join(sorted(self.fuentes))
            raise KeyError(
                f"La fuente '{dataset_id}' no está en catalog/datasets.csv. "
                f"Fuentes disponibles: {disponibles}"
            )
        return self.fuentes[dataset_id]


# --------------------------------------------------------------------------
# Funciones de carga y entorno
# --------------------------------------------------------------------------


def variable_de_entorno(nombre: str) -> str | None:
    """Valor de una variable del entorno o, si no está, del archivo .env del proyecto."""
    if os.environ.get(nombre):
        return os.environ[nombre].strip()
    archivo = PROJECT_ROOT / ".env"
    if not archivo.exists():
        return None
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        clave, _, valor = linea.strip().partition("=")
        if not linea.strip().startswith("#") and clave.removeprefix("export ").strip() == nombre:
            return valor.strip().strip("'\"") or None
    return None


def ensure_directories() -> None:
    """Crea la estructura de directorios de datos si no existe."""
    for directorio in (RAW_DATA_DIR, INTERIM_DATA_DIR, PROCESSED_DATA_DIR, DIR_GEO):
        directorio.mkdir(parents=True, exist_ok=True)


asegurar_directorios = ensure_directories


def leer_catalogo(ruta: Path | None = None) -> dict[str, dict[str, str]]:
    """Filas de catalog/datasets.csv por id_fuente; falla si hay ids repetidos o estados desconocidos."""
    archivo = ruta or ARCHIVO_CATALOGO
    if not archivo.exists():
        return {}
    # utf-8-sig: el catálogo se guarda con BOM para que Excel respete los acentos
    with archivo.open(encoding="utf-8-sig", newline="") as fh:
        filas = list(csv.DictReader(fh))

    catalogo: dict[str, dict[str, str]] = {}
    for fila in filas:
        id_fuente = fila["id_fuente"].strip()
        if id_fuente in catalogo:
            raise ValueError(f"La fuente {id_fuente} está repetida en {archivo.name}.")
        if fila["estado"] not in ESTADOS_FUENTE:
            raise ValueError(
                f"La fuente {id_fuente} tiene el estado '{fila['estado']}' en {archivo.name}; "
                f"los válidos son {', '.join(ESTADOS_FUENTE)}."
            )
        catalogo[id_fuente] = fila
    return catalogo


@functools.lru_cache(maxsize=4)
def cargar_configuracion(ruta: Path | None = None, ruta_catalogo: Path | None = None) -> Configuracion:
    """Carga y valida la configuración del proyecto (cacheada).

    Las fuentes salen del catálogo (catalog/datasets.csv), completadas con sus datos de descarga
    de config/fuentes_health.yaml. Falla si el YAML trae una fuente que no está en el catálogo.
    """
    archivo = ruta or ARCHIVO_FUENTES
    datos: dict[str, Any] = {}
    if archivo.exists():
        with archivo.open(encoding="utf-8") as fh:
            datos = yaml.safe_load(fh) or {}

    umbrales_brutos = datos.get("umbrales") or {}
    umbrales = Umbrales(
        **{
            k: v
            for k, v in umbrales_brutos.items()
            if k in Umbrales.__dataclass_fields__
        }
    )

    catalogo = leer_catalogo(ruta_catalogo)
    descargas = {str(k): v or {} for k, v in (datos.get("fuentes") or {}).items()}
    sin_catalogo = sorted(set(descargas) - set(catalogo))
    if sin_catalogo:
        raise ValueError(
            f"Fuentes en {archivo.name} que no están en catalog/datasets.csv: {', '.join(sin_catalogo)}. "
            "Agréguelas primero al catálogo."
        )

    fuentes: dict[str, FuenteInfo] = {}
    for dataset_id, fila in catalogo.items():
        f = descargas.get(dataset_id, {})
        fuentes[dataset_id] = FuenteInfo(
            dataset_id=dataset_id,
            nombre=fila["nombre"],
            estado=fila["estado"],
            prioridad=fila["prioridad"],
            institucion=fila["institucion"],
            url_fuente=fila["url_fuente"],
            version=fila["version"],
            responsable=fila["responsable"],
            url=str(f.get("url", "")),
            api_base=str(f.get("api_base", "")),
            token_env=str(f.get("token_env", "")),
            nombre_archivo=str(f.get("nombre_archivo", "")),
            limite_diario=f.get("limite_diario"),
            descripcion=str(f.get("descripcion", "")),
            nota=str(f.get("nota", "")),
        )

    excluidas = {
        str(e["cvegeo"]).zfill(9): str(e.get("motivo", ""))
        for e in (datos.get("localidades_excluidas") or [])
        if e.get("cvegeo")
    }

    return Configuracion(fuentes=fuentes, umbrales=umbrales, localidades_excluidas=excluidas)
