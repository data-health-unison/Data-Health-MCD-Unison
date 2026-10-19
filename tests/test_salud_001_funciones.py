"""Pruebas unitarias para el procesamiento de CLUES (salud_001)."""

import pandas as pd
from health_data.processing.salud_001 import (
    limpiar_textos,
    normalizar_categorias,
    agregar_sector,
    validar_coordenadas,
)


def test_limpiar_textos_y_marcadores() -> None:
    """Verifica la limpieza de espacios múltiples y eliminación de marcadores nulos."""
    df = pd.DataFrame(
        {
            "NOMBRE": ["  Hospital   General  ", "SIN NOMBRE", "S/N"],
            "OTRO": ["Centro  de   Salud", "NO ESPECIFICADO", "Texto Normal"],
        }
    )
    resultado = limpiar_textos(df)
    assert resultado["NOMBRE"].iloc[0] == "Hospital General"
    assert pd.isna(resultado["NOMBRE"].iloc[1])
    assert pd.isna(resultado["NOMBRE"].iloc[2])
    assert resultado["OTRO"].iloc[0] == "Centro de Salud"
    assert pd.isna(resultado["OTRO"].iloc[1])


def test_agregar_sector() -> None:
    """Verifica clasificación público vs privado (SMP)."""
    df = pd.DataFrame(
        {"CLAVE DE LA INSTITUCION": ["SSA", "IMSS", "SMP", "ISSSTE"]}
    )
    res = agregar_sector(df)
    assert list(res["sector"]) == ["PUBLICO", "PUBLICO", "PRIVADO", "PUBLICO"]


def test_validar_coordenadas_sonora() -> None:
    """Verifica el filtro de coordenadas dentro del cuadrante geográfico de Sonora."""
    df = pd.DataFrame(
        {
            "LATITUD": [29.07, 19.43, "invalida"],
            "LONGITUD": [-110.95, -99.13, -110.95],
        }
    )
    res = validar_coordenadas(df)
    assert res["fuente_coordenada"].iloc[0] == "CLUES"
    assert res["fuente_coordenada"].iloc[1] == "INVALIDA"
    assert res["fuente_coordenada"].iloc[2] == "INVALIDA"
    assert pd.notna(res["latitud"].iloc[0])
    assert pd.isna(res["latitud"].iloc[1])
    assert pd.isna(res["latitud"].iloc[2])
