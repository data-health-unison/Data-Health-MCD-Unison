"""Análisis experimental de marginación y acceso (health_data.marginacion)."""

import pandas as pd
import pytest

from health_data import marginacion as m
from health_data.config import Umbrales

UMBRALES = Umbrales(tiempo_critico_min=60, tiempo_critico_segundo_nivel_min=120)


@pytest.fixture
def tabla() -> pd.DataFrame:
    """Cuatro localidades: dos con índice propio, una con agregado municipal y una sin dato."""
    return pd.DataFrame(
        {
            "locality_id": ["260030001", "260030002", "260030003", "260990001"],
            "locality_name": ["A", "B", "C", "D"],
            "municipality_name": ["Álamos", "Álamos", "Álamos", "Otro"],
            "population": [100, 50, 2, 10],
            "primary_time_min": [10.0, 70.0, 20.0, 5.0],
            "secondary_time_min": [200.0, 90.0, 150.0, 30.0],
        }
    )


@pytest.fixture
def localidades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cvegeo": ["260030001", "260030002"],
            "grado_marginacion": pd.Categorical(["MUY ALTO", "BAJO"], categories=m.GRADOS, ordered=True),
            "indice_marginacion_norm": [0.4, 0.9],
        }
    )


@pytest.fixture
def agregados() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cve_mun": ["003"],
            "grado_marginacion": pd.Categorical(["MEDIO"], categories=m.GRADOS, ordered=True),
            "indice_marginacion_norm": [0.8],
        }
    )


@pytest.fixture
def unida(tabla, localidades, agregados) -> pd.DataFrame:
    return m.unir_marginacion(tabla, localidades, agregados)


def test_unir_usa_indice_propio_y_luego_agregado(unida):
    assert unida["grado_marginacion"].astype(object).tolist()[:3] == ["MUY ALTO", "BAJO", "MEDIO"]
    assert pd.isna(unida["grado_marginacion"].iloc[3])
    assert unida["marginacion_origen"].tolist()[:3] == [m.ORIGEN_LOCALIDAD, m.ORIGEN_LOCALIDAD, m.ORIGEN_AGREGADO]
    assert pd.isna(unida["marginacion_origen"].iloc[3])
    assert unida["marginacion_norm"].iloc[:3].round(2).tolist() == [0.6, 0.1, 0.2]


def test_unir_no_modifica_la_tabla_original(tabla, localidades, agregados):
    m.unir_marginacion(tabla, localidades, agregados)
    assert "grado_marginacion" not in tabla.columns


def test_clasificar_prioridad(unida):
    prioridad = m.clasificar_prioridad(unida, umbrales=UMBRALES)
    # A: hospital > 120 y muy alta; B: centro de salud > 60 y baja;
    # C: hospital > 120 y media (agregado); D: sin alerta y sin dato.
    assert list(prioridad) == [m.PRIORIDADES[0], m.PRIORIDADES[1], m.PRIORIDADES[1], m.PRIORIDADES[3]]


def test_clasificar_prioridad_marginacion_alta_con_acceso_adecuado(unida):
    unida.loc[1, ["primary_time_min", "secondary_time_min"]] = [10.0, 30.0]
    unida["grado_marginacion"] = unida["grado_marginacion"].astype(object)
    unida.loc[1, "grado_marginacion"] = "ALTO"
    assert m.clasificar_prioridad(unida, umbrales=UMBRALES)[1] == m.PRIORIDADES[2]


def test_acceso_por_grado_solo_indice_propio(unida):
    r = m.acceso_por_grado(unida, umbrales=UMBRALES)
    assert r["localidades"].sum() == 2
    assert r.loc["MUY ALTO", "poblacion_comprometida"] == 100
    assert r.loc["BAJO", "pct_poblacion_comprometida"] == 100
    assert pd.isna(r.loc["MEDIO", "pct_poblacion_comprometida"])


def test_acceso_por_grado_con_agregados(unida):
    r = m.acceso_por_grado(unida, solo_indice_propio=False, umbrales=UMBRALES)
    assert r.loc["MEDIO", "localidades_comprometidas"] == 1


def test_resumen_prioridad(unida):
    r = m.resumen_prioridad(unida, umbrales=UMBRALES)
    assert r["localidades"].sum() == 4
    assert r.loc[m.PRIORIDADES[1], "poblacion"] == 52
    assert r.loc[m.PRIORIDADES[1], "localidades_indice_propio"] == 1
    assert r["pct_poblacion"].sum() == pytest.approx(100)


def test_localidades_doble_carga(unida):
    r = m.localidades_doble_carga(unida, umbrales=UMBRALES)
    assert r["locality_name"].tolist() == ["A"]
