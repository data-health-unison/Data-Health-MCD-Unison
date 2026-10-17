"""Pruebas para el módulo de validación de calidad."""

import pandas as pd
from health_data.validacion import validar_tabla_final


def test_validar_tabla_vacia() -> None:
    """Verifica que una tabla vacía falle limpiamente."""
    rep = validar_tabla_final(pd.DataFrame())
    assert not rep.paso
    assert any(c.nombre == "datos_disponibles" for c in rep.fallidas)


def test_validar_tabla_correcta() -> None:
    """Verifica las reglas sobre un DataFrame sintetizado válido."""
    datos = pd.DataFrame(
        {
            "locality_id": ["260550001", "260180001"],
            "locality_name": ["Hermosillo", "Ciudad Obregón"],
            "municipality_name": ["Hermosillo", "Cajeme"],
            "population": [855000, 320000],
            "latitude": [29.0729, 27.4828],
            "longitude": [-110.9559, -109.9304],
            "primary_candidate_clues": ["SONSSA001", "SONSSA002"],
            "primary_distance_km": [2.5, 3.1],
            "primary_time_min": [5.2, 7.8],
            "primary_routing_status": ["estimated", "estimated"],
            "secondary_candidate_clues": ["SONSSA100", "SONSSA200"],
            "secondary_distance_km": [6.0, 8.5],
            "secondary_time_min": [12.0, 15.0],
            "secondary_routing_status": ["estimated", "estimated"],
            "routing_method": ["estimated", "estimated"],
            "facility_selection_method": ["nearest_geodesic", "nearest_geodesic"],
            "routing_status": ["estimated", "estimated"],
        }
    )
    rep = validar_tabla_final(datos)
    assert rep.paso
    assert len(rep.fallidas) == 0
    cobertura = next(c for c in rep.comprobaciones if c.nombre == "cobertura_real_sakbe")
    assert cobertura.valor == 0.0
    assert "no se reporta como cobertura SAKBÉ" in cobertura.detalle


def test_validar_ruteo_sakbe_real() -> None:
    datos = pd.DataFrame(
        {
            "locality_id": ["260550001"],
            "locality_name": ["Hermosillo"],
            "municipality_name": ["Hermosillo"],
            "population": [855000],
            "latitude": [29.0729],
            "longitude": [-110.9559],
            "primary_candidate_clues": ["SONSSA001"],
            "primary_distance_km": [2.5],
            "primary_time_min": [5.2],
            "primary_routing_status": ["sakbe_ok"],
            "secondary_candidate_clues": ["SONSSA100"],
            "secondary_distance_km": [6.0],
            "secondary_time_min": [12.0],
            "secondary_routing_status": ["sakbe_ok"],
            "routing_method": ["sakbe"],
            "facility_selection_method": ["nearest_geodesic"],
            "routing_status": ["sakbe_ok"],
        }
    )
    rep = validar_tabla_final(datos)
    assert rep.paso
    cobertura = next(c for c in rep.comprobaciones if c.nombre == "cobertura_real_sakbe")
    assert cobertura.valor == 1.0


def test_estatus_ok_legacy_no_se_acepta_como_ruta_real() -> None:
    rep = validar_tabla_final(
        pd.DataFrame(
            {
                "locality_id": ["260550001"],
                "locality_name": ["Hermosillo"],
                "municipality_name": ["Hermosillo"],
                "population": [1],
                "latitude": [29.0],
                "longitude": [-110.0],
                "primary_candidate_clues": ["P1"],
                "primary_distance_km": [1.0],
                "primary_time_min": [3.0],
                "primary_routing_status": ["estimated"],
                "secondary_candidate_clues": ["S1"],
                "secondary_distance_km": [2.0],
                "secondary_time_min": [5.0],
                "secondary_routing_status": ["estimated"],
                "routing_method": ["estimated"],
                "facility_selection_method": ["nearest_geodesic"],
                "routing_status": ["ok"],
            }
        )
    )
    assert not rep.paso
    assert any(c.nombre == "routing_status_coherente" for c in rep.fallidas)


def test_status_sakbe_sin_metricas_falla() -> None:
    datos = {
        "locality_id": ["260550001"],
        "locality_name": ["Hermosillo"],
        "municipality_name": ["Hermosillo"],
        "population": [1],
        "latitude": [29.0],
        "longitude": [-110.0],
        "primary_candidate_clues": ["P1"],
        "primary_distance_km": [None],
        "primary_time_min": [None],
        "primary_routing_status": ["sakbe_ok"],
        "secondary_candidate_clues": ["S1"],
        "secondary_distance_km": [None],
        "secondary_time_min": [None],
        "secondary_routing_status": ["no_route"],
        "routing_method": ["sakbe"],
        "facility_selection_method": ["nearest_geodesic"],
        "routing_status": ["partial"],
    }
    rep = validar_tabla_final(pd.DataFrame(datos))
    assert any(c.nombre == "metricas_y_estado_coherentes" for c in rep.fallidas)
