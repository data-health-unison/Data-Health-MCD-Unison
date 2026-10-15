"""Procesamiento de INEGI-GEO-001: Marco Geoestadístico 2025 de Sonora."""

import geopandas as gpd
import pandas as pd

from health_data.pipeline import (
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    ensure_directories,
)


ARCHIVO_CRUDO = RAW_DATA_DIR / "mg2025_26_sonora.zip"
ARCHIVO_MUNICIPIOS = PROCESSED_DATA_DIR / "inegi-geo-001_municipios.parquet"
ARCHIVO_AMANZANADAS = (
    PROCESSED_DATA_DIR / "inegi-geo-001_localidades_amanzanadas.parquet"
)
ARCHIVO_PUNTUALES = PROCESSED_DATA_DIR / "inegi-geo-001_localidades_puntuales.parquet"

# Codificación de los .dbf. Los .cpg no la escriben igual en todas las capas.
CODIFICACION = "ISO-8859-1"

# Los .prj nombran distinto la proyección, pero sus parámetros son los de EPSG:6372.
EPSG = 6372

M2_POR_KM2 = 1_000_000

# En 26lpr, CVEGEO trae entidad, municipio y localidad (9 dígitos), AGEB y manzana.
DIGITOS_LOCALIDAD = 9

# Categorías que se escriben en mayúsculas y sin acentos, como en SALUD-001.
SIN_ACENTOS = str.maketrans("ÁÉÍÓÚÜ", "AEIOUU")

COLUMNAS_MUNICIPIOS = [
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "municipio",
    "area_km2",
    "geometry",
]

COLUMNAS_AMANZANADAS = [
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "cve_loc",
    "municipio",
    "localidad",
    "ambito",
    "area_km2",
    "geometry",
]

COLUMNAS_PUNTUALES = [
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "cve_loc",
    "cve_ageb",
    "municipio",
    "localidad",
    "plano",
    "en_amanzanadas",
    "geometry",
]


def leer_capa(capa: str) -> gpd.GeoDataFrame:
    """Lee una capa directo del zip, con la codificación de los .dbf y EPSG:6372."""
    ruta = f"/vsizip/{ARCHIVO_CRUDO.as_posix()}/conjunto_de_datos/{capa}.shp"
    crudo = gpd.read_file(ruta, encoding=CODIFICACION)
    return crudo.set_crs(EPSG, allow_override=True)


def claves_como_texto(crudo: pd.DataFrame, columnas: list[str]) -> dict:
    """Copia las claves como texto, con sus ceros, y con su nombre en minúsculas."""
    return {columna.lower(): crudo[columna].astype("string") for columna in columnas}


def sin_espacios_sobrantes(serie: pd.Series) -> pd.Series:
    """Quita los espacios al inicio y al final, y deja uno solo entre palabras."""
    texto = serie.astype("string").str.strip()
    return texto.str.replace(r"\s+", " ", regex=True)


def a_categoria(serie: pd.Series) -> pd.Series:
    """Escribe la categoría en mayúsculas y sin acentos."""
    return serie.astype("string").str.upper().str.translate(SIN_ACENTOS)


def nombre_de_municipio(cve_mun: pd.Series, municipios: gpd.GeoDataFrame) -> pd.Series:
    """Toma el nombre del municipio de la tabla de municipios, por su clave."""
    nombres = municipios.set_index("cve_mun")["municipio"]
    return cve_mun.map(nombres).astype("string")


def ordenar(tabla: gpd.GeoDataFrame, columnas: list[str]) -> gpd.GeoDataFrame:
    """Deja las columnas de salida y ordena por cvegeo."""
    return tabla[columnas].sort_values("cvegeo").reset_index(drop=True)


def procesar_municipios(crudo: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convierte la capa 26mun en la tabla de municipios."""
    municipios = crudo.assign(
        **claves_como_texto(crudo, ["CVEGEO", "CVE_ENT", "CVE_MUN"]),
        municipio=sin_espacios_sobrantes(crudo["NOMGEO"]),
        area_km2=crudo.area / M2_POR_KM2,
    )
    return ordenar(municipios, COLUMNAS_MUNICIPIOS)


def procesar_amanzanadas(
    crudo: gpd.GeoDataFrame, municipios: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Convierte la capa 26l en la tabla de localidades amanzanadas."""
    amanzanadas = crudo.assign(
        **claves_como_texto(crudo, ["CVEGEO", "CVE_ENT", "CVE_MUN", "CVE_LOC"]),
        municipio=nombre_de_municipio(crudo["CVE_MUN"], municipios),
        localidad=sin_espacios_sobrantes(crudo["NOMGEO"]),
        ambito=a_categoria(crudo["AMBITO"]),
        area_km2=crudo.area / M2_POR_KM2,
    )
    return ordenar(amanzanadas, COLUMNAS_AMANZANADAS)


def procesar_puntuales(
    crudo: gpd.GeoDataFrame,
    municipios: gpd.GeoDataFrame,
    amanzanadas: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Convierte la capa 26lpr en la tabla de localidades puntuales, sin CVE_MZA."""
    cvegeo = crudo["CVEGEO"].astype("string").str[:DIGITOS_LOCALIDAD]
    puntuales = crudo.assign(
        **claves_como_texto(crudo, ["CVE_ENT", "CVE_MUN", "CVE_LOC", "CVE_AGEB"]),
        cvegeo=cvegeo,
        municipio=nombre_de_municipio(crudo["CVE_MUN"], municipios),
        localidad=sin_espacios_sobrantes(crudo["NOMGEO"]),
        plano=a_categoria(crudo["PLANO"]),
        en_amanzanadas=cvegeo.isin(amanzanadas["cvegeo"]).astype(bool),
    )
    return ordenar(puntuales, COLUMNAS_PUNTUALES)


def main() -> None:
    """Lee las tres capas, las procesa y guarda cada tabla en GeoParquet."""
    ensure_directories()

    crudos = {capa: leer_capa(capa) for capa in ["26mun", "26l", "26lpr"]}
    municipios = procesar_municipios(crudos["26mun"])
    amanzanadas = procesar_amanzanadas(crudos["26l"], municipios)
    puntuales = procesar_puntuales(crudos["26lpr"], municipios, amanzanadas)

    salidas = [
        (municipios, ARCHIVO_MUNICIPIOS),
        (amanzanadas, ARCHIVO_AMANZANADAS),
        (puntuales, ARCHIVO_PUNTUALES),
    ]
    for tabla, archivo in salidas:
        tabla.to_parquet(archivo, index=False)

    corregidos = sum(
        int(crudo["NOMGEO"].ne(sin_espacios_sobrantes(crudo["NOMGEO"])).sum())
        for crudo in crudos.values()
    )
    print(f"Municipios: {len(municipios)}")
    print(f"Localidades amanzanadas: {len(amanzanadas)}")
    print(amanzanadas["ambito"].value_counts().to_string())
    print(f"Localidades puntuales: {len(puntuales)}")
    print(puntuales["plano"].value_counts().to_string())
    print(f"Claves en las dos capas: {puntuales['en_amanzanadas'].sum()}")
    print(f"Nombres con espacios corregidos: {corregidos}")
    for _, archivo in salidas:
        ruta = archivo.relative_to(PROJECT_ROOT).as_posix()
        print(f"Tabla guardada en: {ruta}")


if __name__ == "__main__":
    main()
