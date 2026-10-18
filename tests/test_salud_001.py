"""Reglas de calidad de la tabla procesada de SALUD-001."""

import pandas as pd
import pytest

from health_data.processing.salud_001 import (
    ARCHIVO_CRUDO,
    ARCHIVO_SALIDA,
    ARCHIVO_VERIFICADAS,
    HOJA,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    contar_en_operacion,
)


pytestmark = pytest.mark.skipif(
    not ARCHIVO_SALIDA.exists(),
    reason="Falta la tabla procesada; se genera con el script de SALUD-001.",
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
    """Columnas del crudo para contar establecimientos y comparar coordenadas."""
    if not ARCHIVO_CRUDO.exists():
        pytest.skip("Falta el archivo crudo de SALUD-001.")
    columnas = [
        "CLUES",
        "CLAVE DE LA ENTIDAD",
        "ESTATUS DE OPERACION",
        "LATITUD",
        "LONGITUD",
    ]
    return pd.read_excel(ARCHIVO_CRUDO, sheet_name=HOJA, usecols=columnas)


@pytest.fixture(scope="module")
def verificadas() -> pd.DataFrame:
    """Revisión manual de coordenadas hecha por el equipo."""
    return pd.read_csv(ARCHIVO_VERIFICADAS)


def test_clues_unicas(tabla: pd.DataFrame) -> None:
    """Comprueba que cada CLUES aparezca una sola vez."""
    assert tabla["clues"].is_unique


def test_registros_dentro_del_total_en_operacion(
    tabla: pd.DataFrame, crudo: pd.DataFrame
) -> None:
    """Comprueba que haya registros y no más que los de Sonora en operación."""
    assert 0 < len(tabla) <= contar_en_operacion(crudo)


def test_revision_manual_aplicada(
    tabla: pd.DataFrame, verificadas: pd.DataFrame
) -> None:
    """Comprueba que no estén los fuera de operación y sí los verificados."""
    resultado = verificadas["resultado"]
    assert resultado.isin(["VERIFICADA", "FUERA DE OPERACION"]).all()
    cerrados = verificadas.loc[resultado.eq("FUERA DE OPERACION"), "clues"]
    revisados = verificadas.loc[resultado.eq("VERIFICADA"), "clues"]
    assert not cerrados.isin(tabla["clues"]).any()
    assert revisados.isin(tabla["clues"]).all()


def test_claves_de_9_digitos(tabla: pd.DataFrame) -> None:
    """Comprueba que la clave geográfica tenga 9 dígitos y empiece con 26."""
    assert tabla["cvegeo"].str.fullmatch(r"26\d{7}").fillna(False).all()


def test_fuentes_de_coordenada(tabla: pd.DataFrame) -> None:
    """Comprueba que la fuente de la coordenada sea CLUES, VERIFICADA o INVALIDA."""
    fuentes = ["CLUES", "VERIFICADA", "INVALIDA"]
    assert tabla["fuente_coordenada"].isin(fuentes).all()


def test_coordenadas_dentro_de_sonora(tabla: pd.DataFrame) -> None:
    """Comprueba que haya coordenadas en Sonora salvo en las de fuente INVALIDA."""
    validas = tabla["fuente_coordenada"].isin(["CLUES", "VERIFICADA"])
    assert tabla.loc[validas, "latitud"].between(LAT_MIN, LAT_MAX).all()
    assert tabla.loc[validas, "longitud"].between(LON_MIN, LON_MAX).all()
    assert tabla.loc[~validas, ["latitud", "longitud"]].isna().all().all()


def test_coordenadas_verificadas_iguales_al_archivo(
    tabla: pd.DataFrame, verificadas: pd.DataFrame
) -> None:
    """Comprueba que las coordenadas VERIFICADA sean exactamente las del archivo."""
    columnas = ["clues", "latitud", "longitud"]
    esperadas = verificadas.loc[verificadas["resultado"].eq("VERIFICADA"), columnas]
    obtenidas = tabla.loc[tabla["fuente_coordenada"].eq("VERIFICADA"), columnas]
    unidas = obtenidas.merge(esperadas, on="clues", suffixes=("", "_archivo"))
    assert len(unidas) == len(obtenidas) == len(esperadas)
    assert unidas["latitud"].eq(unidas["latitud_archivo"]).all()
    assert unidas["longitud"].eq(unidas["longitud_archivo"]).all()


def test_coordenadas_originales_iguales_al_crudo(
    tabla: pd.DataFrame, crudo: pd.DataFrame
) -> None:
    """Comprueba que latitud_original y longitud_original sean las del crudo."""
    original = crudo.set_index("CLUES").loc[tabla["clues"]].reset_index(drop=True)
    assert tabla["latitud_original"].equals(original["LATITUD"])
    assert tabla["longitud_original"].equals(original["LONGITUD"])


def test_sin_nulos_en_columnas_clave(tabla: pd.DataFrame) -> None:
    """Comprueba que las columnas clave no tengan nulos."""
    assert tabla[COLUMNAS_CLAVE].notna().all().all()
