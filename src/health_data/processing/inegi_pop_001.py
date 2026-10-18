"""Procesamiento de INEGI-POP-001: localidades del Censo de Población y Vivienda 2020."""

from __future__ import annotations

import pandas as pd

from health_data.config import (
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    ensure_directories,
)

ARCHIVO_CRUDO = RAW_DATA_DIR / "iter_26csv20.zip"
ARCHIVO_SALIDA = PROCESSED_DATA_DIR / "inegi-pop-001_localidades.parquet"

# Claves de localidad de los totales (0000) y acumulados de una (9998) y dos viviendas (9999)
TOTALES_Y_ACUMULADOS = ["0000", "9998", "9999"]

RENOMBRAR = {
    "ENTIDAD": "cve_ent",
    "MUN": "cve_mun",
    "NOM_MUN": "municipio",
    "LOC": "cve_loc",
    "NOM_LOC": "localidad_original",
    "LATITUD": "latitud",
    "LONGITUD": "longitud",
    "TAMLOC": "tamano_localidad",
    "POBTOT": "poblacion_total",
    "P_3YMAS": "poblacion_3_y_mas",
    "P_60YMAS": "poblacion_60_y_mas",
    "PCON_DISC": "poblacion_con_discapacidad",
    "PSINDER": "poblacion_sin_afiliacion",
    "P3YM_HLI": "poblacion_lengua_indigena",
    "TVIVHAB": "viviendas_habitadas",
    "VIVPARH_CV": "viviendas_con_caracteristicas",
    "VPH_NDACMM": "viviendas_sin_auto_ni_moto",
}

INDICADORES = {
    "pct_60_y_mas": ("poblacion_60_y_mas", "poblacion_total"),
    "pct_con_discapacidad": ("poblacion_con_discapacidad", "poblacion_total"),
    "pct_sin_afiliacion": ("poblacion_sin_afiliacion", "poblacion_total"),
    "pct_lengua_indigena": ("poblacion_lengua_indigena", "poblacion_3_y_mas"),
    "pct_viviendas_sin_auto_ni_moto": (
        "viviendas_sin_auto_ni_moto",
        "viviendas_con_caracteristicas",
    ),
}

CONTEOS = list(dict.fromkeys(c for par in INDICADORES.values() for c in par))
CONTEOS.append("viviendas_habitadas")

MARCAS = {"*": "CONFIDENCIAL", "N/D": "NO DISPONIBLE"}
PATRON_GMS = r"""^(\d{1,3})°(\d{2})'(\d{2}\.\d{3})" ([NSEW])$"""
PERSONAS_POR_VIVIENDA_COLECTIVA = 10

COLUMNAS_SALIDA = [
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "municipio",
    "cve_loc",
    "localidad",
    "localidad_original",
    "latitud",
    "longitud",
    "tamano_localidad",
    "disponibilidad",
    "vivienda_colectiva",
    "poblacion_total",
    "poblacion_60_y_mas",
    "pct_60_y_mas",
    "poblacion_con_discapacidad",
    "pct_con_discapacidad",
    "poblacion_sin_afiliacion",
    "pct_sin_afiliacion",
    "poblacion_3_y_mas",
    "poblacion_lengua_indigena",
    "pct_lengua_indigena",
    "viviendas_habitadas",
    "viviendas_con_caracteristicas",
    "viviendas_sin_auto_ni_moto",
    "pct_viviendas_sin_auto_ni_moto",
]


def leer_crudo() -> pd.DataFrame:
    """Lee el CSV del zip como texto."""
    return pd.read_csv(
        ARCHIVO_CRUDO, dtype=str, encoding="utf-8-sig", keep_default_na=False
    )


def filtrar(crudo: pd.DataFrame) -> pd.DataFrame:
    """Quita totales y acumulados, y deja las columnas que se usan."""
    localidad = ~crudo["LOC"].isin(TOTALES_Y_ACUMULADOS)
    return crudo.loc[localidad, list(RENOMBRAR)].rename(columns=RENOMBRAR)


def agregar_disponibilidad(df: pd.DataFrame) -> pd.DataFrame:
    """Marca si la localidad trae indicadores, es confidencial o no disponible."""
    disponibilidad = pd.Series("COMPLETA", index=df.index, dtype="string")
    for marca, valor in MARCAS.items():
        con_marca = df[CONTEOS].eq(marca).any(axis=1)
        disponibilidad = disponibilidad.mask(con_marca, valor)
    return df.assign(disponibilidad=disponibilidad)


def a_entero(serie: pd.Series) -> pd.Series:
    """Convierte texto con dígitos en entero que admite vacíos."""
    return pd.to_numeric(serie, errors="coerce").astype("Int64")


def convertir_numeros(df: pd.DataFrame) -> pd.DataFrame:
    """Pasa las marcas a vacío y los conteos y el tamaño de localidad a entero."""
    conteos = df[CONTEOS].mask(df[CONTEOS].isin(list(MARCAS)))
    return df.assign(
        **{columna: a_entero(conteos[columna]) for columna in CONTEOS},
        tamano_localidad=a_entero(df["tamano_localidad"]),
    )


def a_grados_decimales(serie: pd.Series) -> pd.Series:
    """Pasa grados, minutos y segundos a grados decimales (negativos al oeste)."""
    partes = serie.str.extract(PATRON_GMS)
    grados = (
        partes[0].astype(float)
        + partes[1].astype(float) / 60
        + partes[2].astype(float) / 3600
    )
    return grados.where(partes[3].isin(["N", "E"]), -grados)


def convertir_coordenadas(df: pd.DataFrame) -> pd.DataFrame:
    """Pasa latitud y longitud a grados decimales."""
    return df.assign(
        latitud=a_grados_decimales(df["latitud"]),
        longitud=a_grados_decimales(df["longitud"]),
    )


def agregar_cvegeo(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega la clave de 9 dígitos y deja las claves como texto."""
    cve_ent = df["cve_ent"].astype("string").str.zfill(2)
    cve_mun = df["cve_mun"].astype("string").str.zfill(3)
    cve_loc = df["cve_loc"].astype("string").str.zfill(4)
    return df.assign(
        cve_ent=cve_ent,
        cve_mun=cve_mun,
        cve_loc=cve_loc,
        cvegeo=cve_ent + cve_mun + cve_loc,
    )


def sin_espacios_sobrantes(serie: pd.Series) -> pd.Series:
    """Quita espacios sobrantes."""
    texto = serie.astype("string").str.strip()
    return texto.str.replace(r"\s+", " ", regex=True)


def limpiar_nombres(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia los nombres y conserva el de la localidad tal como viene."""
    return df.assign(
        municipio=sin_espacios_sobrantes(df["municipio"]),
        localidad=sin_espacios_sobrantes(df["localidad_original"]),
        localidad_original=df["localidad_original"].astype("string"),
    )


def marcar_vivienda_colectiva(df: pd.DataFrame) -> pd.DataFrame:
    """Marca las localidades con más de 10 personas por vivienda habitada."""
    personas = df["poblacion_total"] / df["viviendas_habitadas"]
    colectiva = personas.gt(PERSONAS_POR_VIVIENDA_COLECTIVA).astype(bool)
    return df.assign(vivienda_colectiva=colectiva)


def agregar_porcentajes(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula los porcentajes; vacíos si falta el conteo o el denominador es 0."""
    porcentajes = {}
    for porcentaje, (conteo, denominador) in INDICADORES.items():
        base = df[denominador].mask(df[denominador].eq(0).fillna(False))
        porcentajes[porcentaje] = (df[conteo] / base * 100).astype("float64")
    return df.assign(**porcentajes)


def procesar(crudo: pd.DataFrame) -> pd.DataFrame:
    """Convierte el ITER en la tabla tidy de localidades de Sonora."""
    df = (
        filtrar(crudo)
        .pipe(agregar_disponibilidad)
        .pipe(convertir_numeros)
        .pipe(convertir_coordenadas)
        .pipe(agregar_cvegeo)
        .pipe(limpiar_nombres)
        .pipe(marcar_vivienda_colectiva)
        .pipe(agregar_porcentajes)
    )
    return df[COLUMNAS_SALIDA].sort_values("cvegeo").reset_index(drop=True)


def main() -> None:
    """Lee el crudo, lo procesa y guarda la tabla en Parquet."""
    ensure_directories()

    crudo = leer_crudo()
    tabla = procesar(crudo)
    tabla.to_parquet(ARCHIVO_SALIDA, index=False)

    ruta = ARCHIVO_SALIDA.relative_to(PROJECT_ROOT).as_posix()
    print(f"Localidades ITER: {len(tabla)} de {len(crudo)} filas")
    print(f"Tabla guardada en: {ruta}")


if __name__ == "__main__":
    main()
