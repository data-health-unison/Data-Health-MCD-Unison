"""Pruebas del pipeline principal."""

from health_data.pipeline import ensure_directories


def test_ensure_directories() -> None:
    """Comprueba que los directorios puedan crearse."""
    ensure_directories()