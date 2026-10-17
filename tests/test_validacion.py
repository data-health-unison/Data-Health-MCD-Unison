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
            "nearest_primary_clues": ["SONSSA001", "SONSSA002"],
            "primary_distance_km": [2.5, 3.1],
            "primary_time_min": [5.2, 7.8],
            "nearest_secondary_clues": ["SONSSA100", "SONSSA200"],
            "secondary_distance_km": [6.0, 8.5],
            "secondary_time_min": [12.0, 15.0],
            "routing_status": ["ok", "ok"],
        }
    )
    rep = validar_tabla_final(datos)
    assert rep.paso
    assert len(rep.fallidas) == 0
