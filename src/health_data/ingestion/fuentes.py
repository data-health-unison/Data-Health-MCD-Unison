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

# El procesamiento de INEGI-POP-001 lee el crudo con este nombre.
INEGI_POP_001_ARCHIVO = "iter_26csv20.zip"

# El INEGI lo publica como 26_sonora.zip; el nombre local lleva el año del marco.
INEGI_GEO_001_ARCHIVO = "mg2025_26_sonora.zip"

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
    Fuente(
        dataset_id="INEGI-POP-001",
        nombre="Principales resultados por localidad (ITER)",
        institucion="INEGI, inegi.org.mx",
        url=(
            "https://www.inegi.org.mx/contenidos/programas/ccpv/iter/zip/iter2020/"
            f"{INEGI_POP_001_ARCHIVO}"
        ),
        archivo=INEGI_POP_001_ARCHIVO,
        formato="zip",
        descripcion=(
            "Principales resultados por localidad del Censo de Población y Vivienda "
            "2020 para Sonora. Un CSV con una fila por localidad, más los totales del "
            "estado y de cada municipio y los acumulados de las localidades de una y "
            "dos viviendas."
        ),
        nota=(
            "Las columnas se describen en "
            "https://www.inegi.org.mx/app/scitel/doc/descriptor/fd_iter_cpv2020.pdf."
        ),
    ),
    Fuente(
        dataset_id="INEGI-GEO-001",
        nombre="Marco Geoestadístico 2025",
        institucion="INEGI, inegi.org.mx",
        url=(
            "https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/"
            "espanol/bvinegi/productos/geografia/marcogeo/794551163061/26_sonora.zip"
        ),
        archivo=INEGI_GEO_001_ARCHIVO,
        formato="zip",
        descripcion=(
            "Cartografía de Sonora en shapefile: límites del estado y de los "
            "municipios, AGEB, localidades amanzanadas (polígonos) y rurales "
            "(puntos), manzanas, vialidades y servicios."
        ),
        nota=(
            "Producto 794551163061, con fecha de referencia 31/07/2025 según sus "
            "metadatos. Las coordenadas están en metros (EPSG:6372)."
        ),
    ),
]
