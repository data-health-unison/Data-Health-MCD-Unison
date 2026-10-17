"""Pruebas para las visualizaciones y mapas con Plotly."""

import pandas as pd
from health_data.visualization.mapas import (
    _figura_vacia,
    histograma_tiempos,
    mapa_localidades,
    ranking_municipios,
)


def test_figura_vacia() -> None:
    """Verifica que la figura vacía se cree sin errores."""
    fig = _figura_vacia("Mensaje de prueba")
    assert fig is not None
    assert len(fig.layout.annotations) == 1
    assert fig.layout.annotations[0].text == "Mensaje de prueba"


def test_histograma_tiempos() -> None:
    """Verifica la generación de histograma con umbral crítico."""
    df = pd.DataFrame({"primary_time_min": [15, 30, 45, 60, 90, 120]})
    fig = histograma_tiempos(df)
    assert fig is not None


def test_ranking_municipios() -> None:
    """Verifica el gráfico de ranking de municipios."""
    df = pd.DataFrame(
        {
            "municipality_name": ["Hermosillo", "Cajeme", "Nogales"],
            "primary_time_min": [20.0, 35.5, 45.2],
        }
    )
    fig = ranking_municipios(df, top_n=2)
    assert fig is not None


def test_mapa_localidades() -> None:
    """Verifica la creación del Scattermapbox de localidades."""
    df = pd.DataFrame(
        {
            "latitude": [29.0, 27.5],
            "longitude": [-110.9, -109.9],
            "locality_name": ["Loc 1", "Loc 2"],
            "municipality_name": ["Mun 1", "Mun 2"],
            "primary_time_min": [10.0, 50.0],
            "population": [1000, 200],
        }
    )
    fig = mapa_localidades(df)
    assert fig is not None
