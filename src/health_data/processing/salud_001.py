"""Procesamiento de SALUD-001: establecimientos de salud de Sonora en operación."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from health_data.config import (
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    ensure_directories,
)

log = logging.getLogger(__name__)

ARCHIVO_CRUDO = RAW_DATA_DIR / "ESTABLECIMIENTO_SALUD_202608.xlsx"
HOJA = "CLUES_202608"
ARCHIVO_SALIDA = PROCESSED_DATA_DIR / "salud-001_establecimientos.parquet"
ARCHIVO_VERIFICADAS = (
    PROJECT_ROOT / "references" / "salud-001_coordenadas_verificadas.csv"
)

CLAVE_SONORA = 26
EN_OPERACION = "EN OPERACION"

VERIFICADA = "VERIFICADA"
FUERA_DE_OPERACION = "FUERA DE OPERACION"

# Tipologías móviles que se excluyen del análisis de accesibilidad fija
TIPOLOGIAS_MOVILES = ["P", "UMM", "X", "HM"]

MARCADORES_NULOS = [
    "",
    "NO ESPECIFICADO",
    "SIN NÚMERO",
    "SIN NUMERO",
    "S/N",
    "SIN NOMBRE",
]
CP_SIN_DATO = 99999

# Límites aproximados de Sonora
LAT_MIN, LAT_MAX = 26.0, 32.6
LON_MIN, LON_MAX = -115.2, -108.3

CATEGORICAS = [
    "NOMBRE DE LA INSTITUCION",
    "NOMBRE DE LA INS ADM",
    "NIVEL ATENCION",
    "NOMBRE TIPO ESTABLECIMIENTO",
    "NOMBRE DE TIPOLOGIA",
    "ESTRATO UNIDAD",
    "JURISDICCION",
]
SIN_ACENTOS = str.maketrans("ÁÉÍÓÚÜ", "AEIOUU")

RENOMBRAR = {
    "CLUES": "clues",
    "NOMBRE DE LA UNIDAD": "nombre_unidad",
    "NOMBRE COMERCIAL": "nombre_comercial",
    "CLAVE DE LA INSTITUCION": "clave_institucion",
    "NOMBRE DE LA INSTITUCION": "institucion",
    "NOMBRE DE LA INS ADM": "institucion_administradora",
    "NOMBRE TIPO ESTABLECIMIENTO": "tipo_establecimiento",
    "NOMBRE DE TIPOLOGIA": "tipologia",
    "NIVEL ATENCION": "nivel_atencion",
    "ESTRATO UNIDAD": "estrato",
    "JURISDICCION": "jurisdiccion",
    "MUNICIPIO": "municipio",
    "LOCALIDAD": "localidad",
    "VIALIDAD": "vialidad",
    "NUMERO EXTERIOR": "numero_exterior",
    "ASENTAMIENTO": "asentamiento",
    "LATITUD": "latitud_original",
    "LONGITUD": "longitud_original",
    "OBSERVACIONES AL REGISTRO": "observaciones",
    "COMENTARIOS DE LA VALIDACION": "comentarios_validacion",
}

COLUMNAS_SALIDA = [
    "clues",
    "nombre_unidad",
    "nombre_comercial",
    "clave_institucion",
    "institucion",
    "sector",
    "institucion_administradora",
    "tipo_establecimiento",
    "tipologia",
    "nivel_atencion",
    "estrato",
    "jurisdiccion",
    "cvegeo",
    "cve_ent",
    "cve_mun",
    "municipio",
    "cve_loc",
    "localidad",
    "vialidad",
    "numero_exterior",
    "asentamiento",
    "codigo_postal",
    "fecha_inicio_operacion",
    "latitud",
    "longitud",
    "fuente_coordenada",
    "latitud_original",
    "longitud_original",
    "observaciones",
    "comentarios_validacion",
]


def es_sonora_en_operacion(crudo: pd.DataFrame) -> pd.Series:
    """Marca los establecimientos de Sonora en operación."""
    sonora = crudo["CLAVE DE LA ENTIDAD"].astype(str).str.strip().eq("26") | crudo[
        "CLAVE DE LA ENTIDAD"
    ].eq(CLAVE_SONORA)
    en_operacion = crudo["ESTATUS DE OPERACION"].astype(str).str.strip().eq(EN_OPERACION)
    return sonora & en_operacion


def contar_en_operacion(crudo: pd.DataFrame) -> int:
    """Cuenta los establecimientos de Sonora en operación con móviles incluidas."""
    return int(es_sonora_en_operacion(crudo).sum())


def filtrar(crudo: pd.DataFrame) -> pd.DataFrame:
    """Filtra establecimientos fijos de Sonora en operación."""
    movil = (
        crudo["CLAVE DE TIPOLOGIA"]
        .astype(str)
        .str.strip()
        .isin(TIPOLOGIAS_MOVILES)
    )
    return crudo[es_sonora_en_operacion(crudo) & ~movil].copy()


def limpiar_textos(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia cadenas de texto y normaliza valores nulos."""
    salida = df.copy()
    for columna in salida.select_dtypes("object").columns:
        texto = salida[columna].astype("string").str.strip()
        texto = texto.str.replace(r"\s+", " ", regex=True)
        salida[columna] = texto.mask(texto.str.upper().isin(MARCADORES_NULOS))
    return salida


def normalizar_categorias(df: pd.DataFrame) -> pd.DataFrame:
    """Pasa categorías a mayúsculas y quita acentos."""
    salida = df.copy()
    for columna in CATEGORICAS:
        if columna in salida.columns:
            salida[columna] = (
                salida[columna].astype(str).str.upper().str.translate(SIN_ACENTOS)
            )
    return salida


def agregar_claves(df: pd.DataFrame) -> pd.DataFrame:
    """Genera cvegeo y claves con ceros a la izquierda."""
    cve_ent = df["CLAVE DE LA ENTIDAD"].astype(str).str.strip().str.zfill(2)
    cve_mun = df["CLAVE DEL MUNICIPIO"].astype(str).str.strip().str.zfill(3)
    cve_loc = df["CLAVE DE LA LOCALIDAD"].astype(str).str.strip().str.zfill(4)
    cp = df["CODIGO POSTAL"].mask(df["CODIGO POSTAL"].eq(CP_SIN_DATO))
    return df.assign(
        cve_ent=cve_ent,
        cve_mun=cve_mun,
        cve_loc=cve_loc,
        cvegeo=cve_ent + cve_mun + cve_loc,
        codigo_postal=pd.to_numeric(cp, errors="coerce")
        .astype("Int64")
        .astype("string")
        .str.zfill(5),
    )


def agregar_sector(df: pd.DataFrame) -> pd.DataFrame:
    """Clasifica en sector público o privado."""
    privado = df["CLAVE DE LA INSTITUCION"].astype(str).str.strip().eq("SMP")
    sector = privado.map({True: "PRIVADO", False: "PUBLICO"})
    return df.assign(sector=sector.astype("string"))


def validar_coordenadas(df: pd.DataFrame) -> pd.DataFrame:
    """Comprueba que las coordenadas caigan dentro del rango de Sonora."""
    lat = pd.to_numeric(df["LATITUD"], errors="coerce")
    lon = pd.to_numeric(df["LONGITUD"], errors="coerce")
    valida = lat.between(LAT_MIN, LAT_MAX) & lon.between(LON_MIN, LON_MAX)
    fuente = valida.map({True: "CLUES", False: "INVALIDA"})
    return df.assign(
        latitud=lat.where(valida),
        longitud=lon.where(valida),
        fuente_coordenada=fuente.astype("string"),
    )


def aplicar_verificadas(
    df: pd.DataFrame, verificadas: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Aplica coordenadas corregidas si el archivo existe."""
    if verificadas is None or verificadas.empty:
        return df

    sobran = sorted(set(verificadas["clues"]) - set(df["CLUES"]))
    if sobran:
        log.warning("CLUES en verificadas que no están en el dataframe: %s", sobran[:5])

    resultado = verificadas["resultado"]
    cerrados = verificadas.loc[resultado.eq(FUERA_DE_OPERACION), "clues"]
    nuevas = verificadas[resultado.eq(VERIFICADA)].set_index("clues")

    salida = df[~df["CLUES"].isin(cerrados)].copy()
    verificada = salida["CLUES"].isin(nuevas.index)
    return salida.assign(
        latitud=salida["latitud"].mask(
            verificada, salida["CLUES"].map(nuevas["latitud"])
        ),
        longitud=salida["longitud"].mask(
            verificada, salida["CLUES"].map(nuevas["longitud"])
        ),
        fuente_coordenada=salida["fuente_coordenada"].mask(
            verificada, VERIFICADA
        ),
    )


def procesar(
    crudo: pd.DataFrame, verificadas: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Transforma el catálogo de CLUES en tabla limpia."""
    df = (
        filtrar(crudo)
        .pipe(limpiar_textos)
        .pipe(normalizar_categorias)
        .pipe(agregar_claves)
        .pipe(agregar_sector)
        .pipe(validar_coordenadas)
        .pipe(aplicar_verificadas, verificadas)
    )
    df["fecha_inicio_operacion"] = pd.to_datetime(
        df["FECHA DE INICIO DE OPERACION"], format="%d/%m/%Y", errors="coerce"
    )
    df = df.rename(columns=RENOMBRAR)
    presentes = [c for c in COLUMNAS_SALIDA if c in df.columns]
    return df[presentes].sort_values("clues").reset_index(drop=True)


def main() -> None:
    """Punto de entrada de procesamiento de CLUES."""
    ensure_directories()
    if not ARCHIVO_CRUDO.exists():
        raise FileNotFoundError(f"Falta el archivo crudo: {ARCHIVO_CRUDO}")

    crudo = pd.read_excel(ARCHIVO_CRUDO, sheet_name=HOJA)
    verificadas = (
        pd.read_csv(ARCHIVO_VERIFICADAS)
        if ARCHIVO_VERIFICADAS.exists()
        else None
    )

    tabla = procesar(crudo, verificadas)
    tabla.to_parquet(ARCHIVO_SALIDA, index=False)

    ruta = ARCHIVO_SALIDA.relative_to(PROJECT_ROOT).as_posix()
    print(f"Establecimientos procesados: {len(tabla)}")
    print(f"Nivel de atención:\n{tabla['nivel_atencion'].value_counts()}")
    print(f"Tabla guardada en: {ruta}")


if __name__ == "__main__":
    main()
