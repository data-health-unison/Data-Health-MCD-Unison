"""Procesamiento de CONEVAL-ACC-001: grado de accesibilidad a carretera pavimentada."""

import geopandas as gpd
import pandas as pd

from health_data.pipeline import (
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    ensure_directories,
)


ARCHIVO_CRUDO = RAW_DATA_DIR / "coneval_gacp2020_localidades.zip"
ARCHIVO_SALIDA = PROCESSED_DATA_DIR / "coneval-acc-001_localidades.parquet"

# El shapefile es nacional; se leen solo los atributos de Sonora, sin geometrías.
CAPA = "Localidades_componentes_GACP_CONEVAL.shp"
SONORA = "CVE_ENT = '26'"

# Texto de cada categoría en el crudo y su etiqueta, de mejor a peor acceso. Las
# etiquetas van en mayúsculas y sin acentos, como en SALUD-001; las de C_TP son
# las etiquetas cortas del EDA.
CATEGORIAS = {
    "GACP": {
        "Muy alto": "MUY ALTO",
        "Alto": "ALTO",
        "Medio": "MEDIO",
        "Bajo": "BAJO",
        "Muy bajo": "MUY BAJO",
    },
    "C_TP": {
        "Localidades con 2,500 habitantes o más, o que son cabecera municipal o que "
        "el tiempo de traslado en transporte público a cabecera municipal es menor "
        "a 20 minutos": "2,500 HAB. O MAS, CABECERA O MENOS DE 20 MIN",
        "Tiempo de traslado en transporte público a cabecera municipal de 20 minutos "
        "a 1 hora": "20 MIN A 1 H",
        "Tiempo de traslado en transporte público a cabecera municipal de más de "
        "1 hora a 1.5 horas": "MAS DE 1 H A 1.5 H",
        "Tiempo de traslado en transporte público a cabecera municipal de más de "
        "1.5 horas a 2 horas, o con disponibilidad y tiempo de traslado no "
        "especificada": "MAS DE 1.5 H A 2 H, O NO ESPECIFICADA",
        "Sin transporte público, o tiempos de traslado en transporte público mayor "
        "de 2 horas a cabecera municipal": "SIN TRANSPORTE PUBLICO O MAS DE 2 H",
    },
    "C_CS": {
        "Menos de 1 hr.": "MENOS DE 1 HR.",
        "1 a 2 hrs.": "1 A 2 HRS.",
        "2 a 3 hrs.": "2 A 3 HRS.",
        "3 a 4 hrs.": "3 A 4 HRS.",
        "más de 4 hrs.": "MAS DE 4 HRS.",
    },
    "C_DIS": {
        "<= 1,000": "<= 1,000",
        "> 1,000 y < 2,000": "> 1,000 Y < 2,000",
        ">= 2,000": ">= 2,000",
    },
}

RENOMBRAR = {
    "GACP": "grado_accesibilidad",
    "C_TP": "transporte_publico",
    "C_CS": "tiempo_centro_servicios",
    "C_DIS": "distancia_carretera",
}

# CVE_ENT debe estar aquí: si falta, el filtro de Sonora devuelve 0 filas sin error.
COLUMNAS_CRUDO = ["CVE_ENT", "CVE_MUN", "CVE_LOC", "NOM_MUN", "NOM_LOC", *CATEGORIAS]

COLUMNAS_SALIDA = [
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "cve_loc",
    "municipio",
    "localidad",
    *RENOMBRAR.values(),
]


def leer_crudo() -> pd.DataFrame:
    """Lee los atributos de las localidades de Sonora directo del zip."""
    ruta = f"/vsizip/{ARCHIVO_CRUDO.as_posix()}/{CAPA}"
    crudo = gpd.read_file(
        ruta, columns=COLUMNAS_CRUDO, where=SONORA, ignore_geometry=True
    )
    if crudo.empty:
        raise ValueError(f"No se leyó ninguna localidad con {SONORA}.")
    return crudo


def separar_claves(crudo: pd.DataFrame) -> dict:
    """Separa CVE_LOC en sus partes y comprueba que coincida con CVE_ENT y CVE_MUN."""
    cvegeo = crudo["CVE_LOC"].astype("string")
    fallan = {
        "CVE_LOC sin 9 dígitos": ~cvegeo.str.fullmatch(r"\d{9}").fillna(False),
        "CVE_LOC distinta de CVE_ENT": cvegeo.str[:2].ne(crudo["CVE_ENT"]),
        "CVE_LOC distinta de CVE_MUN": cvegeo.str[:5].ne(crudo["CVE_MUN"]),
    }
    for motivo, falla in fallan.items():
        if falla.any():
            raise ValueError(f"{motivo}: {int(falla.sum())} claves.")
    return {
        "cvegeo": cvegeo,
        "cve_ent": cvegeo.str[:2],
        "cve_mun": cvegeo.str[2:5],
        "cve_loc": cvegeo.str[5:],
    }


def sin_espacios_sobrantes(serie: pd.Series) -> pd.Series:
    """Quita los espacios al inicio y al final, y deja uno solo entre palabras."""
    texto = serie.astype("string").str.strip()
    return texto.str.replace(r"\s+", " ", regex=True)


def a_categoria_ordenada(serie: pd.Series, etiquetas: dict) -> pd.Categorical:
    """Pasa el texto a su etiqueta, ordenada de mejor a peor; falla si no la conoce."""
    fuera = sorted(set(serie.dropna()) - set(etiquetas))
    if fuera or serie.isna().any():
        nulos = int(serie.isna().sum())
        raise ValueError(
            f"{serie.name}: valores fuera de las categorías esperadas {fuera}, "
            f"nulos {nulos}."
        )
    return pd.Categorical(
        serie.map(etiquetas), categories=list(etiquetas.values()), ordered=True
    )


def procesar(crudo: pd.DataFrame) -> pd.DataFrame:
    """Convierte el crudo en la tabla de localidades de Sonora."""
    tabla = pd.DataFrame(
        {
            **separar_claves(crudo),
            "municipio": sin_espacios_sobrantes(crudo["NOM_MUN"]),
            "localidad": sin_espacios_sobrantes(crudo["NOM_LOC"]),
            **{
                nueva: a_categoria_ordenada(crudo[original], CATEGORIAS[original])
                for original, nueva in RENOMBRAR.items()
            },
        }
    )
    return tabla[COLUMNAS_SALIDA].sort_values("cvegeo").reset_index(drop=True)


def main() -> None:
    """Lee el crudo, lo procesa y guarda la tabla en Parquet."""
    ensure_directories()

    crudo = leer_crudo()
    tabla = procesar(crudo)
    tabla.to_parquet(ARCHIVO_SALIDA, index=False)

    ruta = ARCHIVO_SALIDA.relative_to(PROJECT_ROOT).as_posix()
    corregidos = crudo["NOM_LOC"].ne(sin_espacios_sobrantes(crudo["NOM_LOC"])).sum()
    ninguno = tabla["localidad"].str.startswith("Ninguno").sum()
    por_nombre = tabla.groupby(["cve_mun", "localidad"]).size()
    repetidos = por_nombre[por_nombre.gt(1)]
    print(f"Localidades: {len(tabla)}")
    print(f"Municipios: {tabla['cve_mun'].nunique()}")
    for columna in RENOMBRAR.values():
        print(tabla[columna].value_counts(sort=False).to_string())
    print(f"Nombres de localidad con espacios corregidos: {corregidos}")
    print(f'Localidades "Ninguno": {ninguno}')
    print(
        f"Nombres repetidos dentro de su municipio: {len(repetidos)}, "
        f"en {repetidos.sum()} localidades"
    )
    print(f"Tabla guardada en: {ruta}")


if __name__ == "__main__":
    main()
