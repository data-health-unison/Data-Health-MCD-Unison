"""Pruebas del tablero Streamlit con datos sintéticos (sin red ni datos reales)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import health_data.config as config
from health_data.processing import cartografia

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGINAS = [
    "🗺️ Panorama",
    "📊 Municipios",
    "📍 Localidades prioritarias",
    "👥 Grupos vulnerables",
    "📋 Tabla de localidades",
    "🔍 Metodología y fuentes",
]


def _tabla(con_vulnerabilidad: bool = True) -> pd.DataFrame:
    tabla = pd.DataFrame(
        {
            "locality_id": ["260010001", "260010002", "260020001", "260020002"],
            "locality_name": ["Ciudad", "Rancho", "Sierra", "Ejido"],
            "municipality_name": ["A", "A", "B", "B"],
            "population": [1000, 50, 200, 100],
            "latitude": [29.0, 29.2, 28.5, 28.6],
            "longitude": [-110.9, -110.5, -109.0, -109.2],
            "nearest_primary_clues": ["C1", "C1", "C2", "C2"],
            "primary_distance_km": [1.0, 60.0, 10.0, 5.0],
            "primary_time_min": [5.0, 70.0, 20.0, 10.0],
            "primary_method": ["sakbe", "estimado", "sakbe", "sakbe"],
            "nearest_secondary_clues": ["H1", "H1", "H2", "H2"],
            "secondary_distance_km": [2.0, 80.0, 190.0, 40.0],
            "secondary_time_min": [10.0, 90.0, 200.0, 50.0],
            "secondary_method": ["sakbe", "estimado", "sakbe", "sakbe"],
            "routing_status": ["ok", "estimado", "ok", "ok"],
            "routing_consulted_at": ["2026-10-16T10:00:00", "", "2026-10-17T10:00:00", "2026-10-16T11:00:00"],
        }
    )
    if con_vulnerabilidad:
        tabla["poblacion_60_y_mas"] = [100, 10, 40, np.nan]
        tabla["pct_60_y_mas"] = [10.0, 20.0, 20.0, np.nan]
        tabla["pct_viviendas_sin_auto_ni_moto"] = [10.0, 50.0, 25.0, np.nan]
    return tabla


@pytest.fixture
def tablero(tmp_path, monkeypatch):
    """Apunta el tablero a una tabla temporal y evita descargar cartografía."""

    def preparar(tabla: pd.DataFrame | None):
        ruta = tmp_path / "tabla.parquet"
        if tabla is not None:
            tabla.to_parquet(ruta)
        monkeypatch.setattr(config, "ARCHIVO_TABLA_FINAL", ruta)
        monkeypatch.setattr(config, "PROCESSED_DATA_DIR", tmp_path)
        monkeypatch.setattr(config, "ARCHIVO_MANIFIESTO", tmp_path / "manifiesto.json")
        monkeypatch.setattr(cartografia, "asegurar_cartografia", lambda **_: {})
        monkeypatch.setattr(cartografia, "cargar_geojson", lambda *_: None)
        st.cache_data.clear()
        return ruta

    return preparar


def _ejecutar(pagina: str, nivel_indice: int = 0, **sliders) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.radio[0].set_value(pagina)
    at.sidebar.radio[1].set_value(at.sidebar.radio[1].options[nivel_indice])
    for indice, valor in sliders.items():
        at.sidebar.slider[int(indice[-1])].set_value(valor)
    at.run()
    return at


@pytest.mark.parametrize("pagina", PAGINAS)
@pytest.mark.parametrize("nivel", [0, 1])
def test_vistas_sin_errores(tablero, pagina, nivel) -> None:
    tablero(_tabla())
    at = _ejecutar(pagina, nivel)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_panorama_indicadores_y_umbrales(tablero) -> None:
    tablero(_tabla())
    at = _ejecutar("🗺️ Panorama")
    metricas = {m.label: m.value for m in at.metric}
    # Umbrales del proyecto (60 / 120): Rancho (1er nivel 70) y Sierra (2do nivel 200)
    assert metricas["Población con acceso comprometido"] == "250"
    assert metricas["Localidades con acceso comprometido"] == "2 de 4"
    # Con umbral de 2do nivel en 45 min entra también Ejido (50 min)
    at = _ejecutar("🗺️ Panorama", slider1=45)
    assert {m.label: m.value for m in at.metric}["Población con acceso comprometido"] == "350"


def test_cita_de_fuentes_con_fechas_de_consulta(tablero) -> None:
    tablero(_tabla())
    at = _ejecutar("🗺️ Panorama")
    pie = next(c.value for c in at.caption if c.value.startswith("Fuentes:"))
    assert "INEGI, API de Ruteo SAKBÉ v3.1" in pie
    assert "del 2026-10-16 al 2026-10-17" in pie


def test_tabla_sin_variables_de_vulnerabilidad(tablero) -> None:
    """Tablas generadas antes de agregar ITER a la tabla final siguen funcionando."""
    tablero(_tabla(con_vulnerabilidad=False))
    for pagina in PAGINAS:
        at = _ejecutar(pagina)
        assert not at.exception, (pagina, [e.value for e in at.exception])


def test_sin_datos_muestra_bienvenida(tablero) -> None:
    tablero(None)
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("Entorno configurado" in i.value for i in at.info)
