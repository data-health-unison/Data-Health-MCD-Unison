"""Procesamiento de CONAPO-MARG-001 (índice de marginación por localidad 2020)."""

import pandas as pd
import pytest

from health_data.processing.conapo_marg_001 import (
    ARCHIVO_AGREGADOS,
    ARCHIVO_LOCALIDADES,
    COLUMNAS_AGREGADOS,
    COLUMNAS_LOCALIDADES,
    GRADOS,
    a_grado,
    procesar_agregados,
    procesar_localidades,
)

INDICADORES = ["ANALF", "SBASC", "OVSDE", "OVSEE", "OVSAE", "OVPT", "OVHAC", "OVSREF"]


def crudo(filas: list[tuple[str, str, str, str, str]]) -> pd.DataFrame:
    """Crudo mínimo con (MUN, LOC, NOM_LOC, GM_2020, CVE_LOC) por fila."""
    datos = []
    for mun, loc, nombre, grado, cve in filas:
        datos.append(
            {
                "CVE_LOC": cve,
                "ENT": "26",
                "NOM_ENT": "Sonora",
                "MUN": mun,
                "NOM_MUN": "  Álamos ",
                "LOC": loc,
                "NOM_LOC": nombre,
                "POB_TOT": 10.0,
                **{i: 1.5 for i in INDICADORES},
                "IM_2020": 20.0,
                "GM_2020": grado,
                "IMN_2020": 0.7,
            }
        )
    return pd.DataFrame(datos)


def test_a_grado_ordena_de_menor_a_mayor_marginacion():
    grado = a_grado(pd.Series(["Muy alto", "Muy bajo", "Medio"]))
    assert list(grado.categories) == list(GRADOS.values())
    assert grado.ordered
    assert grado.codes[0] > grado.codes[2] > grado.codes[1]


@pytest.mark.parametrize("valor", ["Altísimo", None])
def test_a_grado_falla_con_valores_desconocidos_o_nulos(valor):
    with pytest.raises(ValueError):
        a_grado(pd.Series(["Bajo", valor]))


def test_procesar_localidades():
    tabla = procesar_localidades(
        crudo([("003", "0002", " La  Mina ", "Alto", "260030002"), ("003", "0001", "Álamos", "Bajo", "260030001")])
    )
    assert list(tabla.columns) == COLUMNAS_LOCALIDADES
    assert tabla["cvegeo"].tolist() == ["260030001", "260030002"]
    assert tabla["localidad"].tolist() == ["Álamos", "La Mina"]
    assert tabla["municipio"].eq("Álamos").all()
    assert tabla["grado_marginacion"].tolist() == ["BAJO", "ALTO"]


def test_procesar_localidades_falla_si_la_clave_no_coincide():
    with pytest.raises(ValueError, match="CVE_LOC"):
        procesar_localidades(crudo([("003", "0001", "Álamos", "Bajo", "260040001")]))


def test_procesar_localidades_falla_con_claves_repetidas():
    fila = ("003", "0001", "Álamos", "Bajo", "260030001")
    with pytest.raises(ValueError, match="repetida"):
        procesar_localidades(crudo([fila, fila]))


def test_procesar_agregados():
    tabla = procesar_agregados(
        crudo([("005", "9999", "Localidades de hasta 2 viviendas", "Medio", "260059999"),
               ("003", "9999", "Localidades de hasta 2 viviendas", "Alto", "260039999")])
    )
    assert list(tabla.columns) == COLUMNAS_AGREGADOS
    assert tabla["cve_mun"].tolist() == ["003", "005"]


def test_procesar_agregados_falla_si_trae_localidades_reales():
    with pytest.raises(ValueError, match="9999"):
        procesar_agregados(crudo([("003", "0001", "Álamos", "Bajo", "260030001")]))


@pytest.mark.skipif(
    not (ARCHIVO_LOCALIDADES.exists() and ARCHIVO_AGREGADOS.exists()),
    reason="Faltan las tablas procesadas; se generan con el script de CONAPO-MARG-001.",
)
def test_tablas_procesadas():
    loc = pd.read_parquet(ARCHIVO_LOCALIDADES)
    agr = pd.read_parquet(ARCHIVO_AGREGADOS)
    assert list(loc.columns) == COLUMNAS_LOCALIDADES
    assert list(agr.columns) == COLUMNAS_AGREGADOS
    assert loc["cvegeo"].is_unique and loc["cvegeo"].str.fullmatch(r"26\d{7}").all()
    assert agr["cve_mun"].is_unique
    assert loc["indice_marginacion_norm"].between(0, 1).all()
    assert loc["grado_marginacion"].notna().all() and agr["grado_marginacion"].notna().all()
    # Método DP2: mayor índice, menor marginación; los grados no se traslapan.
    rangos = loc.groupby("grado_marginacion", observed=True)["indice_marginacion"].agg(["min", "max"])
    assert (rangos["min"].iloc[:-1].to_numpy() > rangos["max"].iloc[1:].to_numpy()).all()
