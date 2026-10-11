"""Reglas de calidad de la tabla procesada de SALUD-001."""

import pandas as pd
import pytest

from health_data.processing.salud_001 import (
    ARCHIVO_CRUDO,
    ARCHIVO_SALIDA,
    HOJA,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    contar_en_operacion,
)


pytestmark = pytest.mark.skipif(
    not ARCHIVO_SALIDA.exists(),
    reason="Falta la tabla procesada; ejecuta health_data.processing.salud_001.",
)

COLUMNAS_CLAVE = [
    "clues",
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "cve_loc",
    "municipio",
    "localidad",
    "institucion",
    "sector",
    "nivel_atencion",
    "tipo_establecimiento",
    "fuente_coordenada",
]


@pytest.fixture(scope="module")
def tabla() -> pd.DataFrame:
    """Tabla procesada de establecimientos."""
    return pd.read_parquet(ARCHIVO_SALIDA)


@pytest.fixture(scope="module")
def crudo() -> pd.DataFrame:
    """Columnas del crudo que sirven para contar los establecimientos en operación."""
    if not ARCHIVO_CRUDO.exists():
        pytest.skip("Falta el archivo crudo de SALUD-001.")
    columnas = ["CLAVE DE LA ENTIDAD", "ESTATUS DE OPERACION"]
    return pd.read_excel(ARCHIVO_CRUDO, sheet_name=HOJA, usecols=columnas)


def test_clues_unicas(tabla: pd.DataFrame) -> None:
    """Comprueba que cada CLUES aparezca una sola vez."""
    assert tabla["clues"].is_unique


def test_registros_dentro_del_total_en_operacion(
    tabla: pd.DataFrame, crudo: pd.DataFrame
) -> None:
    """Comprueba que haya registros y no más que los de Sonora en operación."""
    assert 0 < len(tabla) <= contar_en_operacion(crudo)


def test_claves_de_9_digitos(tabla: pd.DataFrame) -> None:
    """Comprueba que la clave geográfica tenga 9 dígitos y empiece con 26."""
    assert tabla["cvegeo"].str.fullmatch(r"26\d{7}").fillna(False).all()


def test_coordenadas_dentro_de_sonora(tabla: pd.DataFrame) -> None:
    """Comprueba que las coordenadas válidas caigan en Sonora y las demás falten."""
    validas = tabla["fuente_coordenada"].eq("CLUES")
    assert tabla.loc[validas, "latitud"].between(LAT_MIN, LAT_MAX).all()
    assert tabla.loc[validas, "longitud"].between(LON_MIN, LON_MAX).all()
    assert tabla.loc[~validas, ["latitud", "longitud"]].isna().all().all()


def test_sin_nulos_en_columnas_clave(tabla: pd.DataFrame) -> None:
    """Comprueba que las columnas clave no tengan nulos."""
    assert tabla[COLUMNAS_CLAVE].notna().all().all()
