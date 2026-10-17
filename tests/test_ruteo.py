"""Pruebas unitarias para el módulo de ruteo y distancias de salud."""

import numpy as np
import pandas as pd
from health_data.processing.ruteo import (
    distancia_haversine,
    estimar_velocidad_promedio,
    emparejar_mas_cercano,
)


def test_distancia_haversine_cero() -> None:
    """La distancia entre el mismo punto debe ser cero."""
    lat = np.array([29.0729])
    lon = np.array([-110.9559])
    dist = distancia_haversine(lat, lon, lat, lon)
    assert np.isclose(dist[0], 0.0, atol=1e-5)


def test_distancia_haversine_conocida() -> None:
    """Distancia aproximada entre Hermosillo y Guaymas (~117 km geodésicos)."""
    lat_hmo, lon_hmo = np.array([29.0729]), np.array([-110.9559])
    lat_gym, lon_gym = np.array([27.9178]), np.array([-110.9089])
    dist = distancia_haversine(lat_hmo, lon_hmo, lat_gym, lon_gym)
    assert 115.0 < dist[0] < 135.0


def test_estimar_velocidad_promedio() -> None:
    """Verifica perfiles de velocidad según longitud del trayecto."""
    distancias = np.array([2.0, 15.0, 40.0, 100.0])
    velocidades = estimar_velocidad_promedio(distancias)
    assert list(velocidades) == [35.0, 50.0, 70.0, 85.0]


def test_emparejar_mas_cercano() -> None:
    """Comprueba el emparejamiento vectorizado al establecimiento más cercano."""
    lats_loc = np.array([29.07, 27.91])
    lons_loc = np.array([-110.95, -110.90])
    facilidades = pd.DataFrame(
        {
            "clues": ["CLUES_HMO", "CLUES_GYM"],
            "latitud": [29.08, 27.92],
            "longitud": [-110.96, -110.91],
        }
    )
    clues_cercano, dist, tiempos = emparejar_mas_cercano(lats_loc, lons_loc, facilidades)
    assert list(clues_cercano) == ["CLUES_HMO", "CLUES_GYM"]
    assert all(tiempos >= 3.0)
