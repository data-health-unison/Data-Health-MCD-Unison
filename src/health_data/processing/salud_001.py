"""Procesamiento de SALUD-001: establecimientos de salud de Sonora en operación."""

import pandas as pd

from health_data.pipeline import (
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    ensure_directories,
)


ARCHIVO_CRUDO = RAW_DATA_DIR / "ESTABLECIMIENTO_SALUD_202608.xlsx"
HOJA = "CLUES_202608"
ARCHIVO_SALIDA = PROCESSED_DATA_DIR / "salud-001_establecimientos.parquet"
ARCHIVO_VERIFICADAS = (
    PROJECT_ROOT / "references" / "salud-001_coordenadas_verificadas.csv"
)

CLAVE_SONORA = 26
EN_OPERACION = "EN OPERACION"

# Resultados de la revisión manual de coordenadas.
VERIFICADA = "VERIFICADA"
FUERA_DE_OPERACION = "FUERA DE OPERACION"

# Unidad móvil, unidad médica móvil, brigada móvil y hospital móvil.
TIPOLOGIAS_MOVILES = ["P", "UMM", "X", "HM"]

# Valores que en la práctica significan "sin dato". Se comparan en mayúsculas.
MARCADORES_NULOS = [
    "",
    "NO ESPECIFICADO",
    "SIN NÚMERO",
    "SIN NUMERO",
    "S/N",
    "SIN NOMBRE",
]
CP_SIN_DATO = 99999

# Caja aproximada que encierra a Sonora (no es el límite real del estado).
LAT_MIN, LAT_MAX = 26.0, 32.6
LON_MIN, LON_MAX = -115.2, -108.3

# Categorías que se escriben en mayúsculas y sin acentos (la Ñ se conserva).
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
    sonora = crudo["CLAVE DE LA ENTIDAD"].eq(CLAVE_SONORA)
    en_operacion = crudo["ESTATUS DE OPERACION"].str.strip().eq(EN_OPERACION)
    return sonora & en_operacion


def contar_en_operacion(crudo: pd.DataFrame) -> int:
    """Cuenta los establecimientos de Sonora en operación, con las unidades móviles."""
    return int(es_sonora_en_operacion(crudo).sum())


def filtrar(crudo: pd.DataFrame) -> pd.DataFrame:
    """Deja los establecimientos de Sonora en operación, sin las unidades móviles."""
    movil = crudo["CLAVE DE TIPOLOGIA"].str.strip().isin(TIPOLOGIAS_MOVILES)
    return crudo[es_sonora_en_operacion(crudo) & ~movil]


def limpiar_textos(df: pd.DataFrame) -> pd.DataFrame:
    """Quita espacios sobrantes y pasa a nulo los valores que significan sin dato."""
    df = df.copy()
    for columna in df.select_dtypes("object").columns:
        texto = df[columna].astype("string").str.strip()
        texto = texto.str.replace(r"\s+", " ", regex=True)
        df[columna] = texto.mask(texto.str.upper().isin(MARCADORES_NULOS))
    return df


def normalizar_categorias(df: pd.DataFrame) -> pd.DataFrame:
    """Escribe las categorías en mayúsculas y sin acentos."""
    df = df.copy()
    for columna in CATEGORICAS:
        df[columna] = df[columna].str.upper().str.translate(SIN_ACENTOS)
    return df


def agregar_claves(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega las claves geográficas y el código postal como texto con sus ceros."""
    cve_ent = df["CLAVE DE LA ENTIDAD"].astype("string").str.zfill(2)
    cve_mun = df["CLAVE DEL MUNICIPIO"].astype("string").str.zfill(3)
    cve_loc = df["CLAVE DE LA LOCALIDAD"].astype("string").str.zfill(4)
    cp = df["CODIGO POSTAL"].mask(df["CODIGO POSTAL"].eq(CP_SIN_DATO))
    return df.assign(
        cve_ent=cve_ent,
        cve_mun=cve_mun,
        cve_loc=cve_loc,
        cvegeo=cve_ent + cve_mun + cve_loc,
        codigo_postal=cp.astype("Int64").astype("string").str.zfill(5),
    )


def agregar_sector(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega el sector: privado si la institución es SMP, público en otro caso."""
    privado = df["CLAVE DE LA INSTITUCION"].eq("SMP")
    sector = privado.map({True: "PRIVADO", False: "PUBLICO"})
    return df.assign(sector=sector.astype("string"))


def validar_coordenadas(df: pd.DataFrame) -> pd.DataFrame:
    """Deja vacías las coordenadas fuera de Sonora o incompletas y marca su fuente."""
    lat, lon = df["LATITUD"], df["LONGITUD"]
    valida = lat.between(LAT_MIN, LAT_MAX) & lon.between(LON_MIN, LON_MAX)
    fuente = valida.map({True: "CLUES", False: "INVALIDA"})
    return df.assign(
        latitud=lat.where(valida),
        longitud=lon.where(valida),
        fuente_coordenada=fuente.astype("string"),
    )


def aplicar_verificadas(df: pd.DataFrame, verificadas: pd.DataFrame) -> pd.DataFrame:
    """Quita los que ya no operan y pone las coordenadas revisadas por el equipo."""
    sobran = sorted(set(verificadas["clues"]) - set(df["CLUES"]))
    if sobran:
        raise ValueError(
            f"{ARCHIVO_VERIFICADAS.name} trae CLUES que no están entre los "
            "establecimientos de Sonora en operación (sin unidades móviles): "
            + ", ".join(sobran)
        )
    resultado = verificadas["resultado"]
    cerrados = verificadas.loc[resultado.eq(FUERA_DE_OPERACION), "clues"]
    nuevas = verificadas[resultado.eq(VERIFICADA)].set_index("clues")

    df = df[~df["CLUES"].isin(cerrados)]
    verificada = df["CLUES"].isin(nuevas.index)
    return df.assign(
        latitud=df["latitud"].mask(verificada, df["CLUES"].map(nuevas["latitud"])),
        longitud=df["longitud"].mask(verificada, df["CLUES"].map(nuevas["longitud"])),
        fuente_coordenada=df["fuente_coordenada"].mask(verificada, VERIFICADA),
    )


def procesar(crudo: pd.DataFrame, verificadas: pd.DataFrame) -> pd.DataFrame:
    """Convierte la hoja de CLUES en la tabla tidy de establecimientos de Sonora."""
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
        df["FECHA DE INICIO DE OPERACION"], format="%d/%m/%Y"
    )
    df = df.rename(columns=RENOMBRAR)
    return df[COLUMNAS_SALIDA].sort_values("clues").reset_index(drop=True)


def main() -> None:
    """Lee el crudo y la revisión manual, los procesa y guarda la tabla en Parquet."""
    ensure_directories()

    crudo = pd.read_excel(ARCHIVO_CRUDO, sheet_name=HOJA)
    verificadas = pd.read_csv(ARCHIVO_VERIFICADAS)
    tabla = procesar(crudo, verificadas)
    tabla.to_parquet(ARCHIVO_SALIDA, index=False)

    ruta = ARCHIVO_SALIDA.relative_to(PROJECT_ROOT).as_posix()
    total = contar_en_operacion(crudo)
    print(f"Establecimientos: {len(tabla)} de {total} en operación")
    print(tabla["fuente_coordenada"].value_counts().to_string())
    print(f"Tabla guardada en: {ruta}")


if __name__ == "__main__":
    main()
