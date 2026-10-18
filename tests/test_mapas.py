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


def test_mapa_localidades_con_metodo() -> None:
    """El tooltip indica si el tiempo fue medido con SAKBÉ o estimado."""
    df = pd.DataFrame(
        {
            "locality_name": ["A", "B"],
            "municipality_name": ["M", "M"],
            "latitude": [29.0, 29.5],
            "longitude": [-110.9, -110.5],
            "population": [100, 5],
            "primary_time_min": [10.0, 80.0],
            "primary_method": ["sakbe", "estimado"],
        }
    )
    fig = mapa_localidades(df, columna_metodo="primary_method")
    assert list(fig.data[0].customdata[:, 3]) == ["medido con SAKBÉ", "estimado"]
    assert "customdata[3]" in fig.data[0].hovertemplate


def test_barras_de_analisis() -> None:
    """Las gráficas del análisis se construyen con las salidas de analisis.py."""
    from health_data.visualization.mapas import (
        barras_grupos_vulnerables,
        barras_municipios_comprometidos,
        barras_poblacion_por_rango,
    )

    rangos = pd.DataFrame(
        {"localidades": [3, 1], "poblacion": [900, 10], "pct_poblacion": [98.9, 1.1]},
        index=["≤ 60 min", "> 60 min"],
    )
    assert len(barras_poblacion_por_rango({"1er nivel": rangos, "2do nivel": rangos}).data) == 2

    resumen = pd.DataFrame(
        {
            "municipio": ["A", "B", "C"],
            "poblacion_comprometida": [50, 20, 0],
            "pct_poblacion_comprometida": [5.0, 40.0, 0.0],
            "tiempo_segundo_ponderado": [130.0, 150.0, 20.0],
        }
    )
    fig = barras_municipios_comprometidos(resumen)
    assert list(fig.data[0].y) == ["B", "A"]  # sin el municipio en cero, el mayor arriba

    sin_afectados = resumen.assign(poblacion_comprometida=0)
    assert len(barras_municipios_comprometidos(sin_afectados).layout.annotations) == 1

    grupos = pd.DataFrame(
        {
            "grupo": ["Población total", "60 años y más"],
            "total_estado": [1000, 100],
            "con_acceso_comprometido": [10, 2],
            "pct_comprometido": [1.0, 2.0],
        }
    )
    assert len(barras_grupos_vulnerables(grupos).data[0].x) == 2


def test_estilo_mapa_base(monkeypatch, tmp_path) -> None:
    """Con CARTO_API_KEY se usa CARTO (con atribución); sin llave, OpenStreetMap."""
    from health_data import config
    from health_data.visualization.mapas import estilo_mapa_base

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)  # sin .env
    monkeypatch.delenv("CARTO_API_KEY", raising=False)
    assert estilo_mapa_base() == {"style": "open-street-map"}

    monkeypatch.setenv("CARTO_API_KEY", "llave-de-prueba")
    estilo = estilo_mapa_base()
    capa = estilo["layers"][0]
    assert estilo["style"] == "white-bg"
    assert capa["source"][0].endswith("?key=llave-de-prueba")
    assert "© CARTO" in capa["sourceattribution"]

    monkeypatch.delenv("CARTO_API_KEY")
    (tmp_path / ".env").write_text("CARTO_API_KEY='desde-env'\n", encoding="utf-8")
    assert estilo_mapa_base()["layers"][0]["source"][0].endswith("?key=desde-env")
