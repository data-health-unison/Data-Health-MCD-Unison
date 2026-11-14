"""Procesamiento de CONAPO-MARG-001: índice de marginación por localidad 2020 (experimental).

El crudo es un .xls dentro de un zip, con una hoja por grupo de entidades y otra con
las localidades de 1 y 2 viviendas agregadas por municipio. CONAPO solo calcula el
índice de las localidades con 3 viviendas habitadas o más.

Salidas:
- ``conapo-marg-001_localidades.parquet``: una fila por localidad de Sonora con índice propio.
- ``conapo-marg-001_agregados_2viv.parquet``: una fila por municipio con el agregado
  de sus localidades de 1 y 2 viviendas.

Método DP2: un índice MAYOR indica MENOR marginación. El normalizado va de 0 a 1 en el
mismo sentido.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from health_data.config import (
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    ensure_directories,
)

ARCHIVO_CRUDO = RAW_DATA_DIR / "conapo_iml2020_localidades.zip"
ARCHIVO_LOCALIDADES = PROCESSED_DATA_DIR / "conapo-marg-001_localidades.parquet"
ARCHIVO_AGREGADOS = PROCESSED_DATA_DIR / "conapo-marg-001_agregados_2viv.parquet"

ARCHIVO_XLS = "IML_2020.xls"
# Sonora (26) está en la hoja de las entidades 16 a 32.
HOJA_LOCALIDADES = "IML_2020_MICH-ZAC"
HOJA_AGREGADOS = "IML_2020_LOC2viv"
SONORA = "26"
LOC_AGREGADO = "9999"

# Grado de marginación del crudo y su etiqueta, de menor a mayor marginación. Mayúsculas y
# sin acentos, como las categorías de CONEVAL-ACC-001.
GRADOS = {
    "Muy bajo": "MUY BAJO",
    "Bajo": "BAJO",
    "Medio": "MEDIO",
    "Alto": "ALTO",
    "Muy alto": "MUY ALTO",
}

CLAVES_TEXTO = {"CVE_LOC": str, "ENT": str, "MUN": str, "LOC": str}

# Indicadores (porcentajes) en el orden del diccionario de CONAPO.
INDICADORES = {
    "ANALF": "pct_analfabeta_15_y_mas",
    "SBASC": "pct_sin_educacion_basica_15_y_mas",
    "OVSDE": "pct_ocupantes_sin_drenaje_ni_excusado",
    "OVSEE": "pct_ocupantes_sin_electricidad",
    "OVSAE": "pct_ocupantes_sin_agua_entubada",
    "OVPT": "pct_ocupantes_piso_de_tierra",
    "OVHAC": "pct_ocupantes_con_hacinamiento",
    "OVSREF": "pct_ocupantes_sin_refrigerador",
}

COLUMNAS_LOCALIDADES = [
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "cve_loc",
    "municipio",
    "localidad",
    "poblacion",
    *INDICADORES.values(),
    "indice_marginacion",
    "indice_marginacion_norm",
    "grado_marginacion",
]

COLUMNAS_AGREGADOS = [
    "cve_ent",
    "cve_mun",
    "municipio",
    "poblacion",
    *INDICADORES.values(),
    "indice_marginacion",
    "indice_marginacion_norm",
    "grado_marginacion",
]


def leer_crudo(ruta=ARCHIVO_CRUDO) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lee las hojas de localidades y de agregados, solo las filas de Sonora."""
    with zipfile.ZipFile(ruta) as zf:
        contenido = io.BytesIO(zf.read(ARCHIVO_XLS))
    hojas = pd.read_excel(
        contenido, sheet_name=[HOJA_LOCALIDADES, HOJA_AGREGADOS], dtype=CLAVES_TEXTO, engine="xlrd"
    )
    localidades = hojas[HOJA_LOCALIDADES].query("ENT == @SONORA").reset_index(drop=True)
    agregados = hojas[HOJA_AGREGADOS].query("ENT == @SONORA").reset_index(drop=True)
    if localidades.empty or agregados.empty:
        raise ValueError(
            f"No se leyeron filas de Sonora (localidades: {len(localidades)}, "
            f"agregados: {len(agregados)}). ¿Cambió la estructura del archivo?"
        )
    return localidades, agregados


def sin_espacios_sobrantes(serie: pd.Series) -> pd.Series:
    """Quita los espacios al inicio y al final, y deja uno solo entre palabras."""
    texto = serie.astype("string").str.strip()
    return texto.str.replace(r"\s+", " ", regex=True)


def a_grado(serie: pd.Series) -> pd.Categorical:
    """Pasa el grado a su etiqueta, ordenada de menor a mayor marginación; falla si no la conoce."""
    fuera = sorted(set(serie.dropna()) - set(GRADOS))
    if fuera or serie.isna().any():
        raise ValueError(
            f"Grado de marginación fuera de las categorías esperadas {fuera}, "
            f"nulos {int(serie.isna().sum())}."
        )
    return pd.Categorical(serie.map(GRADOS), categories=list(GRADOS.values()), ordered=True)


def _comunes(crudo: pd.DataFrame) -> dict:
    """Columnas que comparten las dos tablas."""
    return {
        "cve_ent": crudo["ENT"].astype("string"),
        "cve_mun": crudo["MUN"].astype("string"),
        "municipio": sin_espacios_sobrantes(crudo["NOM_MUN"]),
        "poblacion": pd.to_numeric(crudo["POB_TOT"]).astype("Int64"),
        **{nueva: pd.to_numeric(crudo[original]) for original, nueva in INDICADORES.items()},
        "indice_marginacion": pd.to_numeric(crudo["IM_2020"]),
        "indice_marginacion_norm": pd.to_numeric(crudo["IMN_2020"]),
        "grado_marginacion": a_grado(crudo["GM_2020"]),
    }


def procesar_localidades(crudo: pd.DataFrame) -> pd.DataFrame:
    """Tabla de localidades con índice propio, con la clave cvegeo de 9 dígitos."""
    cvegeo = crudo["CVE_LOC"].astype("string")
    esperada = crudo["ENT"] + crudo["MUN"] + crudo["LOC"]
    fallan = ~cvegeo.str.fullmatch(r"\d{9}").fillna(False) | cvegeo.ne(esperada)
    if fallan.any():
        raise ValueError(f"CVE_LOC no coincide con ENT + MUN + LOC en {int(fallan.sum())} filas.")
    if cvegeo.duplicated().any():
        raise ValueError(f"cvegeo repetida en {int(cvegeo.duplicated().sum())} filas.")
    tabla = pd.DataFrame(
        {
            "cvegeo": cvegeo,
            "cve_loc": crudo["LOC"].astype("string"),
            "localidad": sin_espacios_sobrantes(crudo["NOM_LOC"]),
            **_comunes(crudo),
        }
    )
    return tabla[COLUMNAS_LOCALIDADES].sort_values("cvegeo").reset_index(drop=True)


def procesar_agregados(crudo: pd.DataFrame) -> pd.DataFrame:
    """Tabla municipal del agregado de las localidades de 1 y 2 viviendas."""
    if crudo["LOC"].ne(LOC_AGREGADO).any():
        raise ValueError(f"La hoja {HOJA_AGREGADOS} trae claves de localidad distintas de {LOC_AGREGADO}.")
    tabla = pd.DataFrame(_comunes(crudo))
    if tabla["cve_mun"].duplicated().any():
        raise ValueError("Municipio repetido en los agregados de 1 y 2 viviendas.")
    return tabla[COLUMNAS_AGREGADOS].sort_values("cve_mun").reset_index(drop=True)


def main() -> None:
    """Lee el crudo, lo procesa y guarda las dos tablas en Parquet."""
    ensure_directories()
    crudo_loc, crudo_agr = leer_crudo()
    localidades = procesar_localidades(crudo_loc)
    agregados = procesar_agregados(crudo_agr)
    localidades.to_parquet(ARCHIVO_LOCALIDADES, index=False)
    agregados.to_parquet(ARCHIVO_AGREGADOS, index=False)

    print(f"Localidades con índice propio: {len(localidades):,} ({localidades['poblacion'].sum():,} hab.)")
    print(localidades["grado_marginacion"].value_counts(sort=False).to_string())
    print(
        f"Agregados de 1 y 2 viviendas: {len(agregados)} municipios "
        f"({agregados['poblacion'].sum():,} hab.)"
    )
    for ruta in (ARCHIVO_LOCALIDADES, ARCHIVO_AGREGADOS):
        print(f"Tabla guardada en: {ruta.relative_to(PROJECT_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
