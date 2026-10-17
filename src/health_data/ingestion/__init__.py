"""Módulo de ingesta y descarga de datos.

El cliente de SAKBÉ se importa directamente de ``health_data.ingestion.sakbe``
(no se reexporta aquí para poder ejecutarlo con ``python -m``).
"""

from health_data.ingestion.descarga import (
    ContenidoInvalido,
    ErrorDeDescarga,
    ResultadoDescarga,
    descargar_dataset,
)

__all__ = [
    "descargar_dataset",
    "ResultadoDescarga",
    "ErrorDeDescarga",
    "ContenidoInvalido",
]
