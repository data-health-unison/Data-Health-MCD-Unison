"""Cartografía y procesamiento geoespacial para Sonora.

Descarga y gestiona las capas vectoriales en formato GeoJSON de los 72 municipios
de Sonora (Marco Geoestadístico INEGI) y normaliza claves geoestadísticas y nombres.
"""

from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from pathlib import Path

import pandas as pd
import requests

from health_data.config import DIR_GEO, ensure_directories

log = logging.getLogger(__name__)

# Capa de los 72 municipios de Sonora con commit SHA fijado y verificado por SHA-256
URL_MUNICIPIOS_SONORA = (
    "https://raw.githubusercontent.com/MacWilliXD/INEGI-geojson/"
    "8d38f708dc4acc14afcb461f704bebb43e332a9a/geojson_descargas/AGEM_26.geojson"
)
SHA256_MUNICIPIOS_SONORA = (
    "7d9dd414a87001a54d9dc6afac62a1372cece323b5fe497f82f2e6376e50891b"
)
NOMBRE_MUNICIPIOS_SONORA = DIR_GEO / "sonora_municipios.geojson"

# Capa nacional estatal (32 entidades)
URL_ENTIDADES = (
    "https://raw.githubusercontent.com/angelnmara/geojson/master/mexicoHigh.json"
)
NOMBRE_ENTIDADES = DIR_GEO / "mexico_entidades.geojson"

CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; Data-Health-Sonora/1.0)"}

CLAVES_CVEGEO = ("cvegeo", "CVEGEO", "concat", "adm2_pcode")
CLAVES_CVE_ENT = ("cve_agee", "CVE_ENT", "cve_ent")
CLAVES_NOMBRE = ("nom_agem", "nomgeo", "NOM_MUN", "nom_mun", "shapeName", "name")
PREFIJOS_GENERICOS = {"ESTADO", "MUNICIPIO", "PROVINCIA", "DISTRITO", "REGION"}


def normalizar_nombre(texto: str | None) -> str:
    """Normaliza un nombre quitando acentos, caracteres especiales y colapsando espacios.

    Permite empatar nombres de municipios y localidades entre fuentes distintas
    (ej. 'Álamos' vs 'Alamos').
    """
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    plano = unicodedata.normalize("NFKD", str(texto))
    sin_acentos = "".join(c for c in plano if not unicodedata.combining(c))
    limpio = "".join(c if c.isalnum() or c.isspace() else " " for c in sin_acentos)
    return " ".join(limpio.upper().split())


def _sha256(ruta: Path) -> str:
    """Calcula el hash SHA-256 de un archivo en disco."""
    digest = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _descargar_json(url: str, destino: Path) -> dict | None:
    """Descarga un GeoJSON y comprueba que contenga features válidas."""
    try:
        resp = requests.get(url, timeout=120, headers=CABECERAS)
        resp.raise_for_status()
        datos = resp.json()
    except Exception as exc:
        log.warning("No se pudo descargar %s: %s", url, exc)
        return None

    if not isinstance(datos, dict) or "features" not in datos or not datos.get("features"):
        log.warning("%s no es un GeoJSON válido con features.", url)
        return None

    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False)
    return datos


def asegurar_cartografia(*, forzar: bool = False) -> dict[str, Path | None]:
    """Garantiza que la cartografía municipal y estatal esté descargada y verificada."""
    ensure_directories()
    resultado: dict[str, Path | None] = {"municipios_sonora": None, "entidades": None}

    # 1. Municipios de Sonora
    if NOMBRE_MUNICIPIOS_SONORA.exists() and not forzar:
        resultado["municipios_sonora"] = NOMBRE_MUNICIPIOS_SONORA
        log.info("Cartografía municipal ya presente: %s", NOMBRE_MUNICIPIOS_SONORA.name)
    else:
        datos = _descargar_json(URL_MUNICIPIOS_SONORA, NOMBRE_MUNICIPIOS_SONORA)
        if datos is not None:
            huella = _sha256(NOMBRE_MUNICIPIOS_SONORA)
            if huella != SHA256_MUNICIPIOS_SONORA:
                log.warning(
                    "El GeoJSON municipal tiene sha256 %s, distinto del esperado %s.",
                    huella[:16],
                    SHA256_MUNICIPIOS_SONORA[:16],
                )
            else:
                log.info("Cartografía municipal verificada exitosamente con SHA-256.")
            resultado["municipios_sonora"] = NOMBRE_MUNICIPIOS_SONORA

    # 2. Entidades federativas
    if NOMBRE_ENTIDADES.exists() and not forzar:
        resultado["entidades"] = NOMBRE_ENTIDADES
    else:
        datos_ent = _descargar_json(URL_ENTIDADES, NOMBRE_ENTIDADES)
        if datos_ent is not None:
            resultado["entidades"] = NOMBRE_ENTIDADES

    return resultado


def cargar_geojson(ruta: Path | None) -> dict | None:
    """Carga un GeoJSON desde disco o devuelve None si no existe."""
    if ruta is None or not Path(ruta).exists():
        return None
    with Path(ruta).open(encoding="utf-8") as fh:
        return json.load(fh)


def poner_clave_cvegeo(datos: pd.DataFrame) -> pd.DataFrame:
    """Garantiza la columna 'clave_cvegeo' de 5 dígitos (26XXX) para cruzar con GeoJSON.

    Busca en orden: 'clave_cvegeo', 'cvegeo', 'ubica_geo', o combina 'cve_ent' + 'cve_mun'.
    """
    salida = datos.copy()
    if "clave_cvegeo" in salida.columns and salida["clave_cvegeo"].notna().any():
        salida["clave_cvegeo"] = salida["clave_cvegeo"].astype(str).str.zfill(5)
        return salida
    if "cvegeo" in salida.columns:
        # Si cvegeo tiene 9 dígitos (localidad), tomamos los primeros 5 (municipio)
        salida["clave_cvegeo"] = salida["cvegeo"].astype(str).str[:5].str.zfill(5)
        return salida
    if "ubica_geo" in salida.columns:
        salida["clave_cvegeo"] = salida["ubica_geo"].astype(str).str.zfill(5)
        return salida
    if {"cve_ent", "cve_mun"}.issubset(salida.columns):
        salida["clave_cvegeo"] = (
            salida["cve_ent"].astype(str).str.zfill(2)
            + salida["cve_mun"].astype(str).str.zfill(3)
        )
        return salida
    if "cve_mun" in salida.columns:
        salida["clave_cvegeo"] = "26" + salida["cve_mun"].astype(str).str.zfill(3)
        return salida

    salida["clave_cvegeo"] = pd.NA
    return salida


def alias_entidad(nombre: str | None) -> set[str]:
    """Variantes de nombres de entidades para evitar discrepancias con el GeoJSON."""
    if not nombre:
        return set()
    norm = normalizar_nombre(nombre)
    if not norm:
        return set()

    particulas = {"DE", "DEL", "LA", "LAS", "LOS", "Y"}
    palabras = norm.split()
    corte = next(
        (i for i, palabra in enumerate(palabras) if palabra in particulas), None
    )
    variantes = {norm}
    if corte:
        prefijo = " ".join(palabras[:corte])
        if prefijo not in PREFIJOS_GENERICOS:
            variantes.add(prefijo)
    return variantes
