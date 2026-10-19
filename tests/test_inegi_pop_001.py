"""Reglas de calidad de la tabla procesada de INEGI-POP-001."""

import pandas as pd
import pytest

from health_data.processing.inegi_pop_001 import (
    ARCHIVO_CRUDO,
    ARCHIVO_SALIDA,
    INDICADORES,
    RENOMBRAR,
)


pytestmark = pytest.mark.skipif(
    not ARCHIVO_SALIDA.exists(),
    reason="Falta la tabla procesada; se genera con el script de INEGI-POP-001.",
)

# Claves de localidad de los totales y de los acumulados de una y dos viviendas.
TOTALES_Y_ACUMULADOS = ["0000", "9998", "9999"]

# Caja aproximada que encierra a Sonora, la misma de SALUD-001.
LAT_MIN, LAT_MAX = 26.0, 32.6
LON_MIN, LON_MAX = -115.2, -108.3

# Rango de población de cada tamaño de localidad, según el descriptor del ITER.
RANGOS_TAMANO = {
    1: (1, 249),
    2: (250, 499),
    3: (500, 999),
    4: (1_000, 2_499),
    5: (2_500, 4_999),
    6: (5_000, 9_999),
    7: (10_000, 14_999),
    8: (15_000, 29_999),
    9: (30_000, 49_999),
    10: (50_000, 99_999),
    11: (100_000, 249_999),
    12: (250_000, 499_999),
    13: (500_000, 999_999),
    14: (1_000_000, float("inf")),
}

CODIGO = {nombre: codigo for codigo, nombre in RENOMBRAR.items()}
CONTEOS = [c for c in RENOMBRAR.values() if c.startswith(("poblacion_", "viviendas_"))]
SIN_MARCAS = ["poblacion_total", "viviendas_habitadas"]
CON_MARCAS = [c for c in CONTEOS if c not in SIN_MARCAS]

COLUMNAS_CLAVE = [
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "cve_loc",
    "municipio",
    "localidad",
    "localidad_original",
    "latitud",
    "longitud",
    "tamano_localidad",
    "poblacion_total",
    "viviendas_habitadas",
    "disponibilidad",
    "vivienda_colectiva",
]


@pytest.fixture(scope="module")
def tabla() -> pd.DataFrame:
    """Tabla procesada de localidades."""
    return pd.read_parquet(ARCHIVO_SALIDA)


@pytest.fixture(scope="module")
def crudo() -> pd.DataFrame:
    """Columnas del ITER que usa la tabla, con todas sus filas."""
    if not ARCHIVO_CRUDO.exists():
        pytest.skip("Falta el archivo crudo de INEGI-POP-001.")
    return pd.read_csv(
        ARCHIVO_CRUDO,
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False,
        usecols=list(RENOMBRAR),
    )


@pytest.fixture(scope="module")
def localidades_crudo(crudo: pd.DataFrame) -> pd.DataFrame:
    """Filas del crudo que son localidades, indexadas por su clave de 9 dígitos."""
    localidades = crudo[~crudo["LOC"].isin(TOTALES_Y_ACUMULADOS)]
    cvegeo = localidades["ENTIDAD"] + localidades["MUN"] + localidades["LOC"]
    return localidades.set_index(cvegeo)


@pytest.fixture(scope="module")
def totales_municipales(crudo: pd.DataFrame) -> pd.DataFrame:
    """Filas del crudo con el total de cada municipio."""
    return crudo[crudo["LOC"].eq("0000") & crudo["MUN"].ne("000")]


def test_mismas_localidades_que_el_crudo(
    tabla: pd.DataFrame, localidades_crudo: pd.DataFrame
) -> None:
    """Comprueba que estén todas las localidades del crudo y ninguna más."""
    assert len(tabla) == len(localidades_crudo)
    assert set(tabla["cvegeo"]) == set(localidades_crudo.index)


def test_cvegeo_unica_de_9_digitos(tabla: pd.DataFrame) -> None:
    """Comprueba que cvegeo sea única, de 9 dígitos y que una las tres claves."""
    assert tabla["cvegeo"].is_unique
    assert tabla["cvegeo"].str.fullmatch(r"26\d{7}").fillna(False).all()
    claves = tabla["cve_ent"] + tabla["cve_mun"] + tabla["cve_loc"]
    assert tabla["cvegeo"].eq(claves).fillna(False).all()


def test_mismos_municipios_que_el_crudo(
    tabla: pd.DataFrame, totales_municipales: pd.DataFrame
) -> None:
    """Comprueba que los municipios sean los mismos que los totales municipales."""
    assert set(tabla["cve_mun"]) == set(totales_municipales["MUN"])


def test_poblacion_igual_al_total_estatal(
    tabla: pd.DataFrame, crudo: pd.DataFrame
) -> None:
    """Comprueba que la población de las localidades sume el total del estado."""
    estatal = crudo.loc[crudo["MUN"].eq("000") & crudo["LOC"].eq("0000"), "POBTOT"]
    assert tabla["poblacion_total"].sum() == int(estatal.item())


def test_poblacion_igual_al_total_de_cada_municipio(
    tabla: pd.DataFrame, totales_municipales: pd.DataFrame
) -> None:
    """Comprueba que la población de las localidades sume el total de su municipio."""
    esperada = totales_municipales.set_index("MUN")["POBTOT"].astype(int)
    obtenida = tabla.groupby("cve_mun")["poblacion_total"].sum()
    assert obtenida.to_dict() == esperada.to_dict()


def test_crudo_solo_trae_numeros_o_marcas(localidades_crudo: pd.DataFrame) -> None:
    """Comprueba que los conteos del crudo solo traigan dígitos, "*" o "N/D"."""
    con_marcas = localidades_crudo[[CODIGO[c] for c in CON_MARCAS]]
    assert con_marcas.apply(lambda s: s.str.fullmatch(r"\d+|\*|N/D")).all().all()
    sin_marcas = localidades_crudo[[CODIGO[c] for c in SIN_MARCAS]]
    assert sin_marcas.apply(lambda s: s.str.fullmatch(r"\d+")).all().all()


def test_conteos_no_negativos(tabla: pd.DataFrame) -> None:
    """Comprueba que ningún conteo sea negativo."""
    assert not tabla[CONTEOS].lt(0).any().any()


def test_disponibilidad_igual_a_la_marca_del_crudo(
    tabla: pd.DataFrame, localidades_crudo: pd.DataFrame
) -> None:
    """Comprueba la disponibilidad contra el crudo; solo COMPLETA trae conteos."""
    crudos = localidades_crudo[[CODIGO[c] for c in CON_MARCAS]]
    marca = crudos.where(crudos.isin(["*", "N/D"]), "dato")
    assert marca.nunique(axis=1).eq(1).all()
    nombres = {"*": "CONFIDENCIAL", "N/D": "NO DISPONIBLE", "dato": "COMPLETA"}
    esperada = marca.iloc[:, 0].map(nombres)
    obtenida = tabla.set_index("cvegeo")["disponibilidad"]
    assert obtenida.to_dict() == esperada.to_dict()

    vacios = tabla[CON_MARCAS].isna()
    completa = tabla["disponibilidad"].eq("COMPLETA")
    assert not vacios[completa].any().any()
    assert vacios[~completa].all().all()


def test_confidenciales_son_las_de_1_o_2_viviendas(tabla: pd.DataFrame) -> None:
    """Comprueba que sean CONFIDENCIAL justo las de 1 o 2 viviendas habitadas."""
    confidencial = tabla["disponibilidad"].eq("CONFIDENCIAL")
    una_o_dos = tabla["viviendas_habitadas"].isin([1, 2])
    assert confidencial.eq(una_o_dos).all()


def test_conteos_no_pasan_a_su_denominador(tabla: pd.DataFrame) -> None:
    """Comprueba que ningún conteo sea mayor que su denominador."""
    for conteo, denominador in INDICADORES.values():
        assert not tabla[conteo].gt(tabla[denominador]).any(), conteo


def test_porcentajes(tabla: pd.DataFrame) -> None:
    """Comprueba que cada porcentaje sea conteo / denominador × 100, de 0 a 100."""
    for porcentaje, (conteo, denominador) in INDICADORES.items():
        valor = tabla[porcentaje]
        con_dato = tabla[conteo].notna() & tabla[denominador].gt(0).fillna(False)
        assert valor.notna().eq(con_dato).all(), porcentaje
        assert valor[con_dato].between(0, 100).all(), porcentaje
        datos = tabla[con_dato]
        esperado = datos[conteo].astype(float) / datos[denominador].astype(float) * 100
        assert valor[con_dato].tolist() == pytest.approx(esperado.tolist()), porcentaje


def test_coordenadas_dentro_de_sonora(tabla: pd.DataFrame) -> None:
    """Comprueba que las coordenadas caigan en Sonora y no se repitan."""
    assert tabla["latitud"].between(LAT_MIN, LAT_MAX).all()
    assert tabla["longitud"].between(LON_MIN, LON_MAX).all()
    assert not tabla.duplicated(["latitud", "longitud"]).any()


def test_poblacion_dentro_del_rango_de_su_tamano(tabla: pd.DataFrame) -> None:
    """Comprueba que la población caiga en el rango de su tamaño de localidad."""
    tamano = tabla["tamano_localidad"].astype(int)
    minimo = tamano.map({t: rango[0] for t, rango in RANGOS_TAMANO.items()})
    maximo = tamano.map({t: rango[1] for t, rango in RANGOS_TAMANO.items()})
    poblacion = tabla["poblacion_total"].astype(int)
    assert poblacion.between(minimo, maximo).all()


def test_vivienda_colectiva_con_mas_de_10_por_vivienda(tabla: pd.DataFrame) -> None:
    """Comprueba la marca de más de 10 personas por vivienda habitada."""
    esperada = tabla["poblacion_total"].gt(10 * tabla["viviendas_habitadas"])
    assert tabla["vivienda_colectiva"].eq(esperada).all()


def test_localidad_solo_cambia_en_espacios(tabla: pd.DataFrame) -> None:
    """Comprueba que localidad no tenga espacios de más y solo cambie en espacios."""
    localidad = tabla["localidad"]
    assert localidad.eq(localidad.str.strip()).all()
    assert not localidad.str.contains("  ").any()
    sin_espacios = localidad.str.replace(r"\s+", "", regex=True)
    original = tabla["localidad_original"].str.replace(r"\s+", "", regex=True)
    assert sin_espacios.eq(original).all()


def test_sin_nulos_en_columnas_clave(tabla: pd.DataFrame) -> None:
    """Comprueba que las columnas clave no tengan nulos."""
    assert tabla[COLUMNAS_CLAVE].notna().all().all()


def test_resumen_de_main(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys) -> None:
    """main() imprime el resumen detallado y sus cifras cuadran con la tabla que guarda."""
    if not ARCHIVO_CRUDO.exists():
        pytest.skip("Falta el archivo crudo de INEGI-POP-001.")
    from health_data.processing import inegi_pop_001

    monkeypatch.setattr(inegi_pop_001, "ARCHIVO_SALIDA", tmp_path / "salida.parquet")
    monkeypatch.setattr(inegi_pop_001, "PROJECT_ROOT", tmp_path)
    inegi_pop_001.main()
    salida = capsys.readouterr().out
    generada = pd.read_parquet(tmp_path / "salida.parquet")

    assert f"Localidades: {len(generada)} de " in salida
    assert f"Localidades con vivienda colectiva: {generada['vivienda_colectiva'].sum()}" in salida
    corregidos = generada["localidad"].ne(generada["localidad_original"]).sum()
    assert f"Nombres de localidad con espacios corregidos: {corregidos}" in salida
    for etiqueta in ["Filas de totales y acumulados quitadas:", "Porcentajes vacíos por denominador en 0:", "COMPLETA"]:
        assert etiqueta in salida
