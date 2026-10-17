"""Módulo de visualización y generación de mapas para Data Health MCD Unison."""

from health_data.visualization.mapas import (
    _figura_vacia,
    histograma_tiempos,
    mapa_localidades,
    mapa_municipios,
    ranking_municipios,
)

__all__ = [
    "mapa_municipios",
    "mapa_localidades",
    "histograma_tiempos",
    "ranking_municipios",
    "_figura_vacia",
]
