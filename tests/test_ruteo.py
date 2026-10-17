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


#--------------------------------------------------------------------------
# Ruteo con SAKBÉ (cliente simulado, sin red)
#--------------------------------------------------------------------------

from health_data.ingestion.sakbe import (  #noqa: E402
    Linea,
    Ruta,
    SakbeCuotaAgotada,
    SakbeNoEnCache,
    SakbeSinRuta,
)
from health_data.processing.ruteo import (  #noqa: E402
    ResultadoRuta,
    candidatos_mas_cercanos,
    estado_ruteo,
    mejor_ruta_sakbe,
    rutear_con_sakbe,
)


class ClienteFalso:
    """Simula ClienteSakbe: cada coordenada es un tramo; tiempos por par de tramos."""

    def __init__(self, tiempos=None, sin_linea=(), sin_ruta=(), agotar_en=None):
        self.tiempos = tiempos or {}
        self.sin_linea = set(sin_linea)
        self.sin_ruta = set(sin_ruta)
        self.agotar_en = agotar_en
        self.solo_cache = False
        self.consultas_sesion = 0
        self.rutas_calculadas = []

    def buscar_linea(self, lat, lon):
        if (lat, lon) in self.sin_linea:
            raise SakbeSinRuta("sin línea")
        return Linea(id_routing_net=hash((lat, lon)) % 10_000, source=0, target=1, nombre=f"{lat},{lon}")

    def calcular_ruta(self, origen, destino):
        if self.solo_cache:
            raise SakbeNoEnCache("no en caché")
        if self.agotar_en is not None and len(self.rutas_calculadas) >= self.agotar_en:
            raise SakbeCuotaAgotada("cuota")
        par = (origen.nombre, destino.nombre)
        self.rutas_calculadas.append(par)
        if par in self.sin_ruta:
            raise SakbeSinRuta("sin ruta")
        km, minutos = self.tiempos.get(par, (10.0, 12.0))
        return Ruta(km, minutos, False, 0.0, "", "2026-10-16T12:00:00", False)

    def consultas_restantes(self):
        return 0


def test_candidatos_mas_cercanos_ordenados() -> None:
    fac = pd.DataFrame({"latitud": [29.5, 29.0, 29.2], "longitud": [-111.0, -111.0, -111.0]})
    indices = candidatos_mas_cercanos(np.array([29.01]), np.array([-111.0]), fac, k=2)
    assert indices.tolist() == [[1, 2]]
    #k mayor que el número de establecimientos
    assert candidatos_mas_cercanos(np.array([29.01]), np.array([-111.0]), fac, k=5).shape == (1, 3)


def test_mejor_ruta_elige_el_menor_tiempo_por_carretera() -> None:
    #El candidato más cercano en línea recta es el más lento por carretera
    cliente = ClienteFalso(
        tiempos={
            ("29.0,-111.0", "29.1,-111.0"): (40.0, 50.0),
            ("29.0,-111.0", "29.3,-111.0"): (35.0, 30.0),
        }
    )
    r = mejor_ruta_sakbe(cliente, 29.0, -111.0, [("A", 29.1, -111.0), ("B", 29.3, -111.0)])
    assert (r.estado, r.clues, r.tiempo_min) == ("ok", "B", 30.0)


def test_mejor_ruta_misma_via_no_consulta() -> None:
    cliente = ClienteFalso()
    r = mejor_ruta_sakbe(cliente, 29.0, -111.0, [("A", 29.0, -111.0)])
    assert r.estado == "ok" and r.tiempo_min == 3.0
    assert cliente.rutas_calculadas == []


def test_mejor_ruta_sin_ruta_y_sin_linea() -> None:
    cliente = ClienteFalso(sin_linea={(29.0, -111.0)})
    assert mejor_ruta_sakbe(cliente, 29.0, -111.0, [("A", 29.1, -111.0)]).estado == "sin_ruta"

    cliente = ClienteFalso(sin_ruta={("29.0,-111.0", "29.1,-111.0")})
    assert mejor_ruta_sakbe(cliente, 29.0, -111.0, [("A", 29.1, -111.0)]).estado == "sin_ruta"


def test_cuota_agotada_deja_pendiente_y_pausa_consultas() -> None:
    cliente = ClienteFalso(agotar_en=1)
    r = mejor_ruta_sakbe(cliente, 29.0, -111.0, [("A", 29.1, -111.0), ("B", 29.2, -111.0)])
    assert r.estado == "pendiente"
    assert cliente.solo_cache is True


def test_rutear_prioriza_mayor_poblacion() -> None:
    pop = pd.DataFrame(
        {
            "latitud": [29.0, 30.0, 31.0],
            "longitud": [-111.0, -111.0, -111.0],
            "poblacion_total": [5, 900, 50],
        }
    )
    fac = pd.DataFrame({"clues": ["A", "B"], "latitud": [29.5, 30.5], "longitud": [-111.0, -111.0]})
    cliente = ClienteFalso(agotar_en=2)  #1 localidad (2 candidatos) puede agotar la cuota.
    res = rutear_con_sakbe(pop, {"primer": fac}, cliente, k=2)
    assert [r.estado for r in res["primer"]] == ["pendiente", "ok", "pendiente"]


def test_estado_ruteo() -> None:
    ok, sin, pen = ResultadoRuta("ok"), ResultadoRuta("sin_ruta"), ResultadoRuta("pendiente")
    estados = estado_ruteo([ok, ok, sin, pen], [ok, pen, pen, pen])
    assert estados.tolist() == ["ok", "parcial", "sin_ruta", "estimado"]
