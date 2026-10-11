"""Fuentes que descarga health_data.ingestion.descarga.

Para agregar una fuente basta con agregar una entrada a FUENTES. Su dataset_id
debe estar aprobado en catalog/datasets.csv. La URL se imprime y se guarda en el
registro, así que no debe llevar tokens.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Fuente:
    """Lo necesario para descargar una fuente y describirla."""

    dataset_id: str
    nombre: str
    institucion: str
    url: str
    archivo: str
    formato: str
    descripcion: str
    nota: str = ""


# Periodo del catálogo de establecimientos (AAAAMM). La URL y el nombre del
# archivo se arman con él. Al cambiarlo, revisar la nota de SALUD-001.
SALUD_001_PERIODO = "202608"
SALUD_001_ARCHIVO = f"ESTABLECIMIENTO_SALUD_{SALUD_001_PERIODO}.xlsx"

FUENTES = [
    Fuente(
        dataset_id="SALUD-001",
        nombre="Establecimientos de salud (CLUES)",
        institucion="Secretaría de Salud, gobi.salud.gob.mx",
        url=(
            "https://gobi.salud.gob.mx/gobi/catalogos/catalogosmaestros/"
            f"{SALUD_001_ARCHIVO}"
        ),
        archivo=SALUD_001_ARCHIVO,
        formato="xlsx",
        descripcion=(
            "Catálogo nacional de establecimientos de salud. Una fila por CLUES con "
            "institución, tipología, nivel de atención, estatus de operación, "
            "domicilio, claves geográficas y coordenadas."
        ),
        nota=(
            "El nombre del archivo dice 202608, pero trae movimientos hasta el "
            "22/09/2026."
        ),
    ),
]
