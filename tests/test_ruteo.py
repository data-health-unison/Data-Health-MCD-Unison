"""Pruebas unitarias para el módulo de ruteo y distancias de salud."""

import numpy as np
import pandas as pd
from health_data.processing.ruteo import (
    _establecimientos_por_nivel,
    _rutas_sakbe,
    distancia_haversine,
    estimar_velocidad_promedio,
    emparejar_mas_cercano,
)
from health_data.processing.sakbe import RouteResult, SakbeQuotaExceeded


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


def test_emparejar_con_coordenada_invalida_no_asigna_establecimiento() -> None:
    facilidades = pd.DataFrame(
        {"clues": ["CLUES_HMO"], "latitud": [29.08], "longitud": [-110.96]}
    )
    clues, distancia, tiempo = emparejar_mas_cercano(
        np.array([np.nan]), np.array([-110.95]), facilidades
    )
    assert clues[0] is None
    assert np.isnan(distancia[0])
    assert np.isnan(tiempo[0])


def test_emparejar_ignora_coordenadas_fuera_de_sonora() -> None:
    facilidades = pd.DataFrame(
        {
            "clues": ["FUERA", "DENTRO"],
            "latitud": [40.0, 29.08],
            "longitud": [-110.0, -110.96],
        }
    )
    clues, _, _ = emparejar_mas_cercano(
        np.array([29.07]), np.array([-110.95]), facilidades
    )
    assert clues[0] == "DENTRO"

    clues, distancia, tiempo = emparejar_mas_cercano(
        np.array([40.0]), np.array([-110.95]), facilidades
    )
    assert clues[0] is None
    assert np.isnan(distancia[0])
    assert np.isnan(tiempo[0])


def test_establecimientos_por_nivel_no_reutiliza_todos_como_respaldo() -> None:
    salud = pd.DataFrame(
        {
            "clues": ["PRIMARY"],
            "latitud": [29.0],
            "longitud": [-110.0],
            "nivel_atencion": ["PRIMER NIVEL"],
        }
    )
    try:
        _establecimientos_por_nivel(salud)
    except ValueError as exc:
        assert "segundo nivel" in str(exc)
    else:
        raise AssertionError("Un establecimiento de primer nivel no puede ser fallback.")


def test_rutas_sakbe_conserva_distancia_y_tiempo_del_mismo_destino() -> None:
    class FakeSakbe:
        def __init__(self) -> None:
            self.results = [
                RouteResult(distance_km=18.0, time_min=28.0),
                RouteResult(distance_km=4.0, time_min=7.0),
            ]

        def calcular_ruta(
            self, origen: tuple[float, float], destino: tuple[float, float]
        ) -> RouteResult:
            return self.results.pop(0)

    localidades = pd.DataFrame(
        {"cvegeo": ["260010001"], "latitud": [29.0], "longitud": [-110.0]}
    )
    primer = pd.DataFrame(
        {"clues": ["P1"], "latitud": [29.2], "longitud": [-110.0]}
    )
    segundo = pd.DataFrame(
        {"clues": ["S1"], "latitud": [29.1], "longitud": [-110.0]}
    )
    rutas = _rutas_sakbe(
        localidades,
        primer,
        segundo,
        np.array([0]),
        np.array([0]),
        FakeSakbe(),
    )
    assert rutas.loc[0, "primary_distance_km"] == 18.0
    assert rutas.loc[0, "primary_time_min"] == 28.0
    assert rutas.loc[0, "secondary_distance_km"] == 4.0
    assert rutas.loc[0, "secondary_time_min"] == 7.0
    assert rutas.loc[0, "routing_status"] == "sakbe_ok"


def test_rutas_sakbe_cuota_excedida_no_se_convierte_en_estimada() -> None:
    class FakeSakbe:
        def calcular_ruta(
            self, origen: tuple[float, float], destino: tuple[float, float]
        ) -> RouteResult:
            raise SakbeQuotaExceeded("quota")

    localidades = pd.DataFrame(
        {"cvegeo": ["260010001"], "latitud": [29.0], "longitud": [-110.0]}
    )
    establecimientos = pd.DataFrame(
        {"clues": ["P1"], "latitud": [29.2], "longitud": [-110.0]}
    )
    rutas = _rutas_sakbe(
        localidades,
        establecimientos,
        establecimientos,
        np.array([0]),
        np.array([0]),
        FakeSakbe(),
    )
    assert rutas.loc[0, "primary_routing_status"] == "quota_exceeded"
    assert rutas.loc[0, "secondary_routing_status"] == "quota_exceeded"
    assert rutas.loc[0, "routing_status"] == "quota_exceeded"
    assert pd.isna(rutas.loc[0, "primary_time_min"])
