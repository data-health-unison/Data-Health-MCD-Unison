"""Procesamiento del Índice de Marginación por Localidad de CONAPO, 2020."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from health_data.config import CLAVE_SONORA, PROCESSED_DATA_DIR, RAW_DATA_DIR

ARCHIVO_CRUDO = RAW_DATA_DIR / "IML_2020.xlsx"
ARCHIVO_SALIDA = PROCESSED_DATA_DIR / "conapo-marg-001_localidades.parquet"
HOJA_DATOS = "IML_2020"

INDICADORES = {
    "ANALF": "pct_poblacion_15_y_mas_analfabeta",
    "SBASC": "pct_poblacion_15_y_mas_sin_educacion_basica",
    "OVSDE": "pct_ocupantes_sin_drenaje_ni_excusado",
    "OVSEE": "pct_ocupantes_sin_electricidad",
    "OVSAE": "pct_ocupantes_sin_agua_entubada",
    "OVPT": "pct_ocupantes_con_piso_de_tierra",
    "OVSREF": "pct_ocupantes_sin_refrigerador",
    "OVHAC": "pct_ocupantes_en_hacinamiento",
    "IM_2020": "indice_marginacion",
    "IMN_2020": "indice_marginacion_normalizado",
}
COLUMNAS_CRUDO = ["ENT", "CVE_LOC", "GM_2020", *INDICADORES]


def leer_crudo(ruta: Path | None = None) -> pd.DataFrame:
    """Lee la hoja de datos del libro nacional y conserva las claves como texto."""
    return pd.read_excel(
        ruta or ARCHIVO_CRUDO,
        sheet_name=HOJA_DATOS,
        usecols=COLUMNAS_CRUDO,
        dtype={"ENT": "string", "CVE_LOC": "string", "GM_2020": "string"},
    )


def procesar(crudo: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una fila por localidad de Sonora con los indicadores de CONAPO."""
    es_sonora = crudo["ENT"].astype("string").str.strip().eq(CLAVE_SONORA)
    datos = crudo.loc[es_sonora, COLUMNAS_CRUDO]
    if datos.empty:
        raise ValueError("El índice de marginación no contiene localidades de Sonora.")

    clave = datos["CVE_LOC"].astype("string").str.strip()
    if not clave.str.fullmatch(rf"{CLAVE_SONORA}[0-9]{{7}}").fillna(False).all():
        raise ValueError("El índice de marginación contiene claves de Sonora inválidas.")
    if clave.duplicated().any():
        raise ValueError("El índice de marginación contiene claves de localidad duplicadas.")

    tabla = datos[list(INDICADORES)].apply(pd.to_numeric).rename(columns=INDICADORES)
    tabla.insert(0, "cvegeo", clave)
    tabla.insert(1, "grado_marginacion", datos["GM_2020"].astype("string").str.strip())
    return tabla.sort_values("cvegeo").reset_index(drop=True)


def main(*, ruta_cruda: Path | None = None, ruta_salida: Path | None = None) -> None:
    """Guarda el Parquet de marginación por localidad."""
    salida = ruta_salida or ARCHIVO_SALIDA
    tabla = procesar(leer_crudo(ruta_cruda))
    salida.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_parquet(salida, index=False)
    print(f"CONAPO: {len(tabla)} localidades guardadas en {salida.name}.")


if __name__ == "__main__":
    main()
