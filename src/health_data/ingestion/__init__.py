"""Módulo de ingesta y descarga de datos."""

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
