"""Pruebas de los indicadores de accesibilidad y vulnerabilidad."""

import numpy as np
import pandas as pd
import pytest

from health_data.analisis import (
    acceso_comprometido,
    cortes_por_nivel,
    localidades_prioritarias,
    poblacion_por_rango,
    preparar_tabla,
    resumen_estatal,
    resumen_municipal,
)
from health_data.config import Umbrales

UMBRALES = Umbrales(tiempo_critico_min=60, tiempo_muy_critico_min=120, tiempo_critico_segundo_nivel_min=180)


@pytest.fixture
def tabla() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "locality_id": ["260010001", "260010002", "260020001", "260020002", "260020003"],
            "locality_name": ["Ciudad", "Rancho", "Sierra", "Ejido", "Confidencial"],
            "municipality_name": ["A", "A", "B", "B", "B"],
            "population": [1000, 50, 200, 100, 3],
            "primary_time_min": [5.0, 70.0, 20.0, 10.0, 130.0],
            "primary_method": ["sakbe", "estimado", "sakbe", "sakbe", "estimado"],
            "secondary_time_min": [10.0, 90.0, 200.0, 50.0, 190.0],
            "secondary_method": ["sakbe", "estimado", "sakbe", "sakbe", "estimado"],
            "routing_status": ["ok", "estimado", "ok", "ok", "estimado"],
            "poblacion_60_y_mas": [100, 10, 40, 20, np.nan],
            "poblacion_con_discapacidad": [50, 5, 30, 10, np.nan],
            "pct_viviendas_sin_auto_ni_moto": [10.0, 50.0, 25.0, 0.0, np.nan],
        }
    )


def test_cortes_por_nivel() -> None:
    assert cortes_por_nivel("primer", UMBRALES) == [0, 30, 60, 120, np.inf]
    assert cortes_por_nivel("segundo", UMBRALES) == [0, 60, 120, 180, np.inf]
    with pytest.raises(ValueError):
        cortes_por_nivel("tercer", UMBRALES)


def test_poblacion_sin_auto_estimada(tabla) -> None:
    t = preparar_tabla(tabla)
    assert t["poblacion_sin_auto_estimada"].tolist()[:4] == [100, 25, 50, 0]
    assert np.isnan(t["poblacion_sin_auto_estimada"].iloc[4])


def test_acceso_comprometido(tabla) -> None:
    # Rancho (1er > 60), Sierra (2do > 180) y Confidencial (ambos)
    assert acceso_comprometido(tabla, umbrales=UMBRALES).tolist() == [False, True, True, False, True]
    # Con umbral de 2do nivel más estricto entra también Rancho por 2do nivel (90 > 60)
    assert acceso_comprometido(tabla, umbral_segundo=60, umbrales=UMBRALES).sum() == 3


def test_poblacion_por_rango(tabla) -> None:
    r = poblacion_por_rango(tabla, "primer", UMBRALES)
    assert r.index.tolist() == ["≤ 30 min", "30–60 min", "60–120 min", "> 120 min"]
    assert r["poblacion"].tolist() == [1300, 0, 50, 3]
    assert r["localidades"].sum() == 5
    assert r["pct_poblacion"].sum() == pytest.approx(100)
    assert r.loc["60–120 min", "poblacion_60_y_mas"] == 10


def test_resumen_municipal(tabla) -> None:
    r = resumen_municipal(tabla, umbrales=UMBRALES).set_index("municipio")
    # B tiene más población comprometida (Sierra 200 + Confidencial 3) que A (Rancho 50)
    assert r.index.tolist() == ["B", "A"]
    assert r["cvegeo"].tolist() == ["26002", "26001"]
    assert r.loc["B", "poblacion_comprometida"] == 203
    assert r.loc["B", "poblacion_segundo_critico"] == 203
    assert r.loc["A", "poblacion_primer_critico"] == 50
    assert r.loc["B", "poblacion_60_y_mas_comprometida"] == 40  # el NaN no suma
    assert r.loc["A", "pct_poblacion_comprometida"] == pytest.approx(100 * 50 / 1050)
    # Promedio ponderado por población: (1000*5 + 50*70) / 1050
    assert r.loc["A", "tiempo_primer_ponderado"] == pytest.approx(8500 / 1050)
    assert r.loc["A", "pct_localidades_sakbe"] == pytest.approx(50)


def test_localidades_prioritarias(tabla) -> None:
    r = localidades_prioritarias(tabla, n=2, umbrales=UMBRALES)
    assert r["locality_name"].tolist() == ["Sierra", "Rancho"]
    assert len(localidades_prioritarias(tabla, n=None, umbrales=UMBRALES)) == 3


def test_resumen_estatal(tabla) -> None:
    r = resumen_estatal(tabla, umbrales=UMBRALES)
    assert r["poblacion"] == 1353
    assert r["poblacion_comprometida"] == 253
    assert r["pct_localidades_sakbe"] == pytest.approx(60)
    assert r["pct_poblacion_sakbe"] == pytest.approx(100 * 1300 / 1353)
    assert r["pct_poblacion_con_datos_vulnerabilidad"] == pytest.approx(100 * 1350 / 1353)


def test_tabla_sin_variables_de_vulnerabilidad(tabla) -> None:
    """Funciona con tablas generadas antes de agregar las variables de ITER."""
    minima = tabla.drop(columns=["poblacion_60_y_mas", "poblacion_con_discapacidad", "pct_viviendas_sin_auto_ni_moto"])
    assert resumen_municipal(minima, umbrales=UMBRALES)["poblacion_comprometida"].sum() == 253
    assert poblacion_por_rango(minima, "segundo", UMBRALES)["poblacion"].sum() == 1353
    assert resumen_estatal(minima, umbrales=UMBRALES)["pct_poblacion_con_datos_vulnerabilidad"] == 0


def test_umbral_de_2do_nivel_del_proyecto() -> None:
    """El equipo fijó 120 min para el 2do nivel; 180 se conserva como corte de rango."""
    from health_data.analisis import umbral_critico
    from health_data.config import cargar_configuracion

    umbrales = cargar_configuracion().umbrales
    assert umbral_critico("segundo", umbrales) == 120
    assert cortes_por_nivel("segundo", umbrales) == [0, 60, 120, 180, np.inf]


def test_grupos_vulnerables(tabla) -> None:
    from health_data.analisis import grupos_vulnerables

    r = grupos_vulnerables(tabla, umbrales=UMBRALES).set_index("grupo")
    assert r.index[0] == "Población total"
    assert r.loc["Población total", "con_acceso_comprometido"] == 253
    # 60+: Rancho 10 + Sierra 40 (Confidencial sin dato) de 170 en el estado
    assert r.loc["60 años y más", "con_acceso_comprometido"] == 50
    assert r.loc["60 años y más", "pct_comprometido"] == pytest.approx(100 * 50 / 170)
    # Sin vehículo estimada: Rancho 25 + Sierra 50
    assert r.loc["Sin automóvil ni motocicleta (estimada)", "con_acceso_comprometido"] == 75


def test_resumen_estatal_tiempos_ponderados(tabla) -> None:
    r = resumen_estatal(tabla, umbrales=UMBRALES)
    esperado = (1000 * 5 + 50 * 70 + 200 * 20 + 100 * 10 + 3 * 130) / 1353
    assert r["tiempo_primer_ponderado"] == pytest.approx(esperado)
