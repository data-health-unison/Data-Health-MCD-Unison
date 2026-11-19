"""Procesamiento de INEGI-RESLOC-001: transporte público por localidad, 2020."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from health_data.config import (
    CLAVE_SONORA,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
)
from health_data.processing.inegi_pop_001 import agregar_cvegeo

ARCHIVO_CRUDO = RAW_DATA_DIR / "resloc_26csv2020.zip"
ARCHIVO_SALIDA = PROCESSED_DATA_DIR / "inegi-resloc-001_localidades.parquet"
CSV_DATOS = "RESLOC_26CSV2020.csv"

CLAVES = {"ENT": "cve_ent", "MUN": "cve_mun", "LOC": "cve_loc"}
MODOS_CABECERA = {
    "C_AUTOCAB": "autobus_a_cabecera",
    "C_MICROCAB": "micro_colectivo_a_cabecera",
    "C_CAMIONCAB": "camion_redilas_a_cabecera",
    "C_TAXICAB": "taxi_a_cabecera",
    "C_BICICAB": "bicitaxi_a_cabecera",
    "C_BARCOCAB": "barco_a_cabecera",
}
DISPONIBILIDAD = {"1": "SI", "3": "NO", "9": "NO ESPECIFICADO"}
MEDIO_PRINCIPAL = {
    "1": "AUTOBUS O CAMION",
    "2": "MICRO, COMBI O TAXI COLECTIVO",
    "3": "CAMION DE REDILAS O TROCA",
    "4": "TAXI LIBRE O DE SITIO",
    "5": "BICITAXI O MOTOTAXI",
    "6": "BARCO, PANGA O LANCHA COLECTIVA",
    "9": "NO ESPECIFICADO",
}
FRECUENCIA = {
    "1": "SIN SALIDA DIARIA",
    "2": "1 A 5",
    "3": "6 A 14",
    "4": "15 A 29",
    "5": "30 O MAS",
    "9": "NO ESPECIFICADO",
}
COLUMNAS_CRUDO = [
    *CLAVES,
    "C_DIS_TRANS",
    *MODOS_CABECERA,
    "C_TRANSPRIN",
    "C_FRECUENCIA",
    "C_TIEMPO",
]


def leer_crudo(ruta: Path | None = None) -> pd.DataFrame:
    """Lee el CSV de datos, que viene en el ZIP junto con el descriptor."""
    with ZipFile(ruta or ARCHIVO_CRUDO) as archivo:
        with archivo.open(CSV_DATOS) as contenido:
            return pd.read_csv(
                contenido,
                encoding="latin-1",
                usecols=COLUMNAS_CRUDO,
                dtype="string",
                keep_default_na=False,
            )


def etiquetar(codigos: pd.Series, etiquetas: dict[str, str]) -> pd.Series:
    """Conserva las respuestas no especificadas y los blancos por separado."""
    desconocidos = sorted(set(codigos.dropna()) - etiquetas.keys() - {""})
    if desconocidos:
        raise ValueError(f"{codigos.name}: códigos de RESLOC desconocidos {desconocidos}.")
    return codigos.map(etiquetas).astype("string")


def procesar(crudo: pd.DataFrame) -> pd.DataFrame:
    """Convierte los campos de transporte en una tabla por localidad de Sonora."""
    datos = crudo[COLUMNAS_CRUDO].astype("string")
    datos = datos.apply(lambda columna: columna.str.strip())
    datos = datos.loc[datos["ENT"].eq(CLAVE_SONORA)]
    if datos.empty:
        raise ValueError("RESLOC no contiene localidades de Sonora.")

    for campo, longitud in (("ENT", 2), ("MUN", 3), ("LOC", 4)):
        validas = datos[campo].str.fullmatch(rf"[0-9]{{1,{longitud}}}").fillna(False)
        if not validas.all():
            raise ValueError(f"RESLOC contiene {int((~validas).sum())} claves {campo} inválidas.")

    claves = agregar_cvegeo(datos[list(CLAVES)].rename(columns=CLAVES))
    if claves["cvegeo"].duplicated().any():
        raise ValueError("RESLOC contiene claves de localidad duplicadas.")

    tiempo = pd.to_numeric(datos["C_TIEMPO"].replace({"": pd.NA, "999": pd.NA}))
    tabla = claves[["cvegeo", *CLAVES.values()]].assign(
        transporte_foraneo=etiquetar(datos["C_DIS_TRANS"], DISPONIBILIDAD),
        **{
            nombre: etiquetar(datos[campo], DISPONIBILIDAD)
            for campo, nombre in MODOS_CABECERA.items()
        },
        medio_principal_cabecera=etiquetar(datos["C_TRANSPRIN"], MEDIO_PRINCIPAL),
        frecuencia_salidas_cabecera=etiquetar(datos["C_FRECUENCIA"], FRECUENCIA),
        tiempo_cabecera_min=tiempo.astype("Int64"),
    )
    return tabla.sort_values("cvegeo").reset_index(drop=True)


def main(*, ruta_cruda: Path | None = None, ruta_salida: Path | None = None) -> None:
    """Prepara el Parquet de transporte público para el cruce por cvegeo."""
    salida = ruta_salida or ARCHIVO_SALIDA
    tabla = procesar(leer_crudo(ruta_cruda))
    salida.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_parquet(salida, index=False)
    print(f"RESLOC: {len(tabla)} localidades guardadas en {salida.name}.")


if __name__ == "__main__":
    main()
