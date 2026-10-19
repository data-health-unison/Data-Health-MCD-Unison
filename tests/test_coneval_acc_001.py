"""Reglas de calidad de la tabla procesada de CONEVAL-ACC-001."""

import pandas as pd
import pytest

from health_data.processing.coneval_acc_001 import ARCHIVO_SALIDA


pytestmark = pytest.mark.skipif(
    not ARCHIVO_SALIDA.exists(),
    reason="Falta la tabla procesada; se genera con el script de CONEVAL-ACC-001.",
)

# Ã y Â aparecen cuando un texto en UTF-8 se lee como ISO-8859-1; � es el
# carácter de reemplazo.
MAL_CODIFICADO = r"Ã|Â|�"

COLUMNAS = [
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "cve_loc",
    "municipio",
    "localidad",
    "grado_accesibilidad",
    "transporte_publico",
    "tiempo_centro_servicios",
    "distancia_carretera",
]

COLUMNAS_CLAVE = ["cvegeo", "cve_ent", "cve_mun", "cve_loc", "municipio", "localidad"]

NOMBRES = ["municipio", "localidad"]

COMPONENTES = ["transporte_publico", "tiempo_centro_servicios", "distancia_carretera"]

# Categorías de cada columna, de mejor a peor acceso.
ESPERADAS = {
    "grado_accesibilidad": ["MUY ALTO", "ALTO", "MEDIO", "BAJO", "MUY BAJO"],
    "transporte_publico": [
        "2,500 HAB. O MAS, CABECERA O MENOS DE 20 MIN",
        "20 MIN A 1 H",
        "MAS DE 1 H A 1.5 H",
        "MAS DE 1.5 H A 2 H, O NO ESPECIFICADA",
        "SIN TRANSPORTE PUBLICO O MAS DE 2 H",
    ],
    "tiempo_centro_servicios": [
        "MENOS DE 1 HR.",
        "1 A 2 HRS.",
        "2 A 3 HRS.",
        "3 A 4 HRS.",
        "MAS DE 4 HRS.",
    ],
    "distancia_carretera": ["<= 1,000", "> 1,000 Y < 2,000", ">= 2,000"],
}


@pytest.fixture(scope="module")
def tabla() -> pd.DataFrame:
    """Tabla procesada de localidades."""
    return pd.read_parquet(ARCHIVO_SALIDA)


def cumplen_patron(serie: pd.Series, patron: str) -> bool:
    """Indica si todos los valores siguen el patrón completo."""
    return bool(serie.str.fullmatch(patron).fillna(False).all())


def test_columnas(tabla: pd.DataFrame) -> None:
    """Comprueba que la tabla tenga exactamente las columnas de salida, en orden."""
    assert list(tabla.columns) == COLUMNAS


def test_cvegeo_unica_de_9_digitos(tabla: pd.DataFrame) -> None:
    """Comprueba que cvegeo sea única, de 9 dígitos y que una las tres claves."""
    assert tabla["cvegeo"].is_unique
    assert cumplen_patron(tabla["cvegeo"], r"26\d{7}")
    assert cumplen_patron(tabla["cve_ent"], r"\d{2}")
    assert cumplen_patron(tabla["cve_mun"], r"\d{3}")
    assert cumplen_patron(tabla["cve_loc"], r"\d{4}")
    claves = tabla["cve_ent"] + tabla["cve_mun"] + tabla["cve_loc"]
    assert tabla["cvegeo"].eq(claves).fillna(False).all()


def test_municipios_de_001_a_072(tabla: pd.DataFrame) -> None:
    """Comprueba que las claves de municipio vayan de 001 a 072, sin faltantes."""
    esperadas = {f"{numero:03d}" for numero in range(1, 73)}
    assert set(tabla["cve_mun"]) == esperadas


def test_categorias_ordenadas(tabla: pd.DataFrame) -> None:
    """Comprueba que cada categoría esté ordenada, con sus valores y sin nulos."""
    for columna, categorias in ESPERADAS.items():
        serie = tabla[columna]
        assert isinstance(serie.dtype, pd.CategoricalDtype), columna
        assert serie.cat.ordered, columna
        assert list(serie.cat.categories) == categorias, columna
        assert serie.notna().all(), columna


def test_cada_combinacion_da_un_solo_grado(tabla: pd.DataFrame) -> None:
    """Comprueba que cada combinación de los tres componentes dé un solo grado."""
    grados = tabla.groupby(COMPONENTES, observed=True)["grado_accesibilidad"]
    assert grados.nunique().eq(1).all()


def test_sin_nulos_en_columnas_clave(tabla: pd.DataFrame) -> None:
    """Comprueba que las columnas clave no tengan nulos."""
    assert tabla[COLUMNAS_CLAVE].notna().all().all()


def test_sin_nombres_mal_codificados(tabla: pd.DataFrame) -> None:
    """Comprueba que ningún nombre traiga Ã, Â o el carácter de reemplazo."""
    for columna in NOMBRES:
        mal = tabla[columna].str.contains(MAL_CODIFICADO).fillna(False)
        assert not mal.any(), columna


def test_sin_espacios_de_mas(tabla: pd.DataFrame) -> None:
    """Comprueba que los nombres no tengan espacios al inicio, al final ni dobles."""
    for columna in NOMBRES:
        nombre = tabla[columna]
        assert nombre.eq(nombre.str.strip()).fillna(False).all(), columna
        assert not nombre.str.contains("  ").fillna(False).any(), columna
