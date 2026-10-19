"""Reglas de calidad de las tablas procesadas de INEGI-GEO-001."""

import geopandas as gpd
import pandas as pd
import pytest

from health_data.processing.inegi_geo_001 import (
    ARCHIVO_AMANZANADAS,
    ARCHIVO_MUNICIPIOS,
    ARCHIVO_PUNTUALES,
)


ARCHIVOS = [ARCHIVO_MUNICIPIOS, ARCHIVO_AMANZANADAS, ARCHIVO_PUNTUALES]

pytestmark = pytest.mark.skipif(
    not all(archivo.exists() for archivo in ARCHIVOS),
    reason="Faltan las tablas procesadas; se generan con el script de INEGI-GEO-001.",
)

# Ã y Â aparecen cuando un texto en UTF-8 se lee como ISO-8859-1; � es el
# carácter de reemplazo.
MAL_CODIFICADO = r"Ã|Â|�"

COLUMNAS_CLAVE = {
    "municipios": ["cvegeo", "cve_ent", "cve_mun", "municipio", "area_km2"],
    "amanzanadas": [
        "cvegeo",
        "cve_ent",
        "cve_mun",
        "cve_loc",
        "municipio",
        "localidad",
        "ambito",
        "area_km2",
    ],
    "puntuales": [
        "cvegeo",
        "cve_ent",
        "cve_mun",
        "cve_loc",
        "cve_ageb",
        "municipio",
        "localidad",
        "plano",
        "en_amanzanadas",
    ],
}


@pytest.fixture(scope="module")
def municipios() -> gpd.GeoDataFrame:
    """Tabla procesada de municipios."""
    return gpd.read_parquet(ARCHIVO_MUNICIPIOS)


@pytest.fixture(scope="module")
def amanzanadas() -> gpd.GeoDataFrame:
    """Tabla procesada de localidades amanzanadas."""
    return gpd.read_parquet(ARCHIVO_AMANZANADAS)


@pytest.fixture(scope="module")
def puntuales() -> gpd.GeoDataFrame:
    """Tabla procesada de localidades puntuales."""
    return gpd.read_parquet(ARCHIVO_PUNTUALES)


@pytest.fixture(scope="module")
def tablas(
    municipios: gpd.GeoDataFrame,
    amanzanadas: gpd.GeoDataFrame,
    puntuales: gpd.GeoDataFrame,
) -> dict[str, gpd.GeoDataFrame]:
    """Las tres tablas, por nombre."""
    return {
        "municipios": municipios,
        "amanzanadas": amanzanadas,
        "puntuales": puntuales,
    }


def cumplen_patron(serie: pd.Series, patron: str) -> bool:
    """Indica si todos los valores siguen el patrón completo."""
    return bool(serie.str.fullmatch(patron).fillna(False).all())


def cve_mun_espacial(
    puntos: gpd.GeoDataFrame, municipios: gpd.GeoDataFrame
) -> pd.Series:
    """Clave del municipio donde cae cada punto; vacía si no cae en ninguno."""
    unido = gpd.sjoin(
        puntos[["geometry"]],
        municipios[["cve_mun", "geometry"]],
        how="left",
        predicate="within",
    )
    return unido["cve_mun"]


def test_claves_de_municipios(municipios: gpd.GeoDataFrame) -> None:
    """Comprueba que cvegeo sea única, de 5 dígitos y que una sus dos claves."""
    assert municipios["cvegeo"].is_unique
    assert cumplen_patron(municipios["cvegeo"], r"26\d{3}")
    assert cumplen_patron(municipios["cve_ent"], r"\d{2}")
    assert cumplen_patron(municipios["cve_mun"], r"\d{3}")
    claves = municipios["cve_ent"] + municipios["cve_mun"]
    assert municipios["cvegeo"].eq(claves).fillna(False).all()


def test_claves_de_localidades(
    amanzanadas: gpd.GeoDataFrame, puntuales: gpd.GeoDataFrame
) -> None:
    """Comprueba que cvegeo sea única, de 9 dígitos y que una sus tres claves."""
    for nombre, tabla in [("amanzanadas", amanzanadas), ("puntuales", puntuales)]:
        assert tabla["cvegeo"].is_unique, nombre
        assert cumplen_patron(tabla["cvegeo"], r"26\d{7}"), nombre
        assert cumplen_patron(tabla["cve_ent"], r"\d{2}"), nombre
        assert cumplen_patron(tabla["cve_mun"], r"\d{3}"), nombre
        assert cumplen_patron(tabla["cve_loc"], r"\d{4}"), nombre
        claves = tabla["cve_ent"] + tabla["cve_mun"] + tabla["cve_loc"]
        assert tabla["cvegeo"].eq(claves).fillna(False).all(), nombre


def test_clave_de_ageb(puntuales: gpd.GeoDataFrame) -> None:
    """Comprueba que la clave de AGEB tenga 3 dígitos y un dígito o una letra."""
    assert cumplen_patron(puntuales["cve_ageb"], r"\d{3}[0-9A-Z]")


def test_municipios_de_001_a_072(municipios: gpd.GeoDataFrame) -> None:
    """Comprueba que las claves de municipio vayan de 001 a 072, sin faltantes."""
    esperadas = {f"{numero:03d}" for numero in range(1, 73)}
    assert set(municipios["cve_mun"]) == esperadas


def test_geometrias_validas_y_no_vacias(tablas: dict[str, gpd.GeoDataFrame]) -> None:
    """Comprueba que las geometrías existan, no estén vacías y sean válidas."""
    for nombre, tabla in tablas.items():
        assert tabla.geometry.notna().all(), nombre
        assert not tabla.geometry.is_empty.any(), nombre
        assert tabla.geometry.is_valid.all(), nombre


def test_epsg_6372(tablas: dict[str, gpd.GeoDataFrame]) -> None:
    """Comprueba que las tres tablas estén en EPSG:6372."""
    for nombre, tabla in tablas.items():
        assert tabla.crs is not None, nombre
        assert tabla.crs.to_epsg() == 6372, nombre


def test_amanzanadas_en_su_municipio(
    amanzanadas: gpd.GeoDataFrame, municipios: gpd.GeoDataFrame
) -> None:
    """Comprueba que el punto interior de cada localidad caiga en su municipio."""
    puntos = amanzanadas.assign(geometry=amanzanadas.representative_point())
    espacial = cve_mun_espacial(puntos, municipios)
    assert espacial.index.equals(amanzanadas.index)
    assert espacial.eq(amanzanadas["cve_mun"]).fillna(False).all()


def test_puntuales_en_su_municipio(
    puntuales: gpd.GeoDataFrame, municipios: gpd.GeoDataFrame
) -> None:
    """Comprueba que el punto de cada localidad caiga en su municipio."""
    espacial = cve_mun_espacial(puntuales, municipios)
    assert espacial.index.equals(puntuales.index)
    assert espacial.eq(puntuales["cve_mun"]).fillna(False).all()


def test_en_amanzanadas_igual_a_plano_si(puntuales: gpd.GeoDataFrame) -> None:
    """Comprueba que en_amanzanadas sea verdadero justo cuando plano es SI."""
    plano_si = puntuales["plano"].eq("SI").fillna(False)
    assert puntuales["en_amanzanadas"].eq(plano_si).all()


def test_en_las_dos_capas_son_las_amanzanadas_rurales(
    amanzanadas: gpd.GeoDataFrame, puntuales: gpd.GeoDataFrame
) -> None:
    """Comprueba que las claves en las dos capas sean las amanzanadas rurales."""
    en_las_dos = set(amanzanadas["cvegeo"]) & set(puntuales["cvegeo"])
    marcadas = puntuales.loc[puntuales["en_amanzanadas"], "cvegeo"]
    rural = amanzanadas["ambito"].eq("RURAL").fillna(False)
    assert set(marcadas) == en_las_dos
    assert set(amanzanadas.loc[rural, "cvegeo"]) == en_las_dos


def test_sin_nombres_mal_codificados(tablas: dict[str, gpd.GeoDataFrame]) -> None:
    """Comprueba que ningún nombre traiga Ã, Â o el carácter de reemplazo."""
    for nombre, tabla in tablas.items():
        for columna in ["municipio", "localidad"]:
            if columna in tabla:
                mal = tabla[columna].str.contains(MAL_CODIFICADO).fillna(False)
                assert not mal.any(), f"{nombre}: {columna}"


def test_sin_nulos_en_columnas_clave(tablas: dict[str, gpd.GeoDataFrame]) -> None:
    """Comprueba que las columnas clave no tengan nulos."""
    for nombre, tabla in tablas.items():
        assert tabla[COLUMNAS_CLAVE[nombre]].notna().all().all(), nombre
