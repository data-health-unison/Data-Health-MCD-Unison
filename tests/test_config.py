"""Pruebas de la configuración central de Data Health."""

from health_data.config import (
    cargar_configuracion,
    ensure_directories,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
)


def test_ensure_directories() -> None:
    """Verifica que los directorios se creen sin error."""
    ensure_directories()
    assert RAW_DATA_DIR.exists()
    assert PROCESSED_DATA_DIR.exists()


def test_cargar_configuracion() -> None:
    """Comprueba la carga de fuentes_health.yaml y los umbrales."""
    cfg = cargar_configuracion()
    assert cfg.umbrales.tiempo_critico_min == 60
    assert cfg.umbrales.tiempo_muy_critico_min == 120
    assert "CONEVAL-ACC-001" in cfg.fuentes
    fuente = cfg.fuente("CONEVAL-ACC-001")
    assert fuente.estado == "approved"


def test_localidades_excluidas() -> None:
    """Las localidades de la Isla del Tiburón están excluidas, cada una con su motivo."""
    excluidas = cargar_configuracion().localidades_excluidas
    assert set(excluidas) == {"260302192", "260303379", "260303436"}
    assert all("Isla del Tiburón" in motivo for motivo in excluidas.values())
