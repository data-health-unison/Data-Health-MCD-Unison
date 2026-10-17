"""Pruebas de normalización y cartografía de Sonora."""

import pandas as pd
from health_data.processing.cartografia import (
    normalizar_nombre,
    poner_clave_cvegeo,
    alias_entidad,
)


def test_normalizar_nombre() -> None:
    """Verifica que se eliminen acentos, mayúsculas y caracteres especiales."""
    assert normalizar_nombre("Álamos") == "ALAMOS"
    assert normalizar_nombre("San Luis Río Colorado") == "SAN LUIS RIO COLORADO"
    assert normalizar_nombre("Hermosillo   ") == "HERMOSILLO"
    assert normalizar_nombre(None) == ""


def test_poner_clave_cvegeo() -> None:
    """Verifica la generación de la clave municipal de 5 dígitos (26XXX)."""
    df1 = pd.DataFrame({"cve_mun": ["001", "072"]})
    res1 = poner_clave_cvegeo(df1)
    assert list(res1["clave_cvegeo"]) == ["26001", "26072"]

    df2 = pd.DataFrame({"cvegeo": ["260550001", "260180001"]})
    res2 = poner_clave_cvegeo(df2)
    assert list(res2["clave_cvegeo"]) == ["26055", "26018"]


def test_alias_entidad() -> None:
    """Verifica que entidades con nombres compuestos generen sus alias."""
    alias = alias_entidad("Coahuila de Zaragoza")
    assert "COAHUILA" in alias
    assert "COAHUILA DE ZARAGOZA" in alias
