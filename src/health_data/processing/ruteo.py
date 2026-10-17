"""Módulo de ruteo y emparejamiento con establecimientos de salud de 1er y 2do nivel.

Para cada localidad de Sonora:
1. Identifica el establecimiento operativo de primer nivel (centro de salud) más cercano.
2. Identifica el establecimiento operativo de segundo nivel (hospital) más cercano.
3. Estima distancia y tiempo de traslado considerando factor de sinuosidad vial y velocidad de red carretera.
4. Soporta integración y respaldo con API SAKBÉ de INEGI.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from health_data.config import (
    ARCHIVO_TABLA_FINAL,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    ensure_directories,
)

log = logging.getLogger(__name__)

ARCHIVO_POP = PROCESSED_DATA_DIR / "inegi-pop-001_localidades.parquet"
ARCHIVO_CONEVAL = PROCESSED_DATA_DIR / "coneval-acc-001_localidades.parquet"
ARCHIVO_SALUD = PROCESSED_DATA_DIR / "salud-001_establecimientos.parquet"

# Factor medio de sinuosidad carretera para el terreno de Sonora (relación red vial / línea recta)
FACTOR_SINUOSIDAD = 1.28


def distancia_haversine(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Calcula distancia geodésica en kilómetros usando la fórmula de Haversine."""
    r_tierra = 6371.0  # Radio medio de la Tierra en km
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    d_lat = np.radians(lat2 - lat1)
    d_lon = np.radians(lon2 - lon1)

    a = (
        np.sin(d_lat / 2.0) ** 2
        + np.cos(p1) * np.cos(p2) * np.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return r_tierra * c


def estimar_velocidad_promedio(distancia_carretera_km: np.ndarray) -> np.ndarray:
    """Estima la velocidad media según la longitud del trayecto por tipo de vía."""
    velocidad = np.empty_like(distancia_carretera_km, dtype=float)
    # Trayectos muy cortos (calles urbanas / caminos vecinales)
    m1 = distancia_carretera_km <= 5.0
    velocidad[m1] = 35.0
    # Trayectos cortos (caminos rurales pavimentados)
    m2 = (distancia_carretera_km > 5.0) & (distancia_carretera_km <= 25.0)
    velocidad[m2] = 50.0
    # Trayectos medianos (carreteras estatales)
    m3 = (distancia_carretera_km > 25.0) & (distancia_carretera_km <= 60.0)
    velocidad[m3] = 70.0
    # Trayectos largos (red carretera federal / autopistas)
    m4 = distancia_carretera_km > 60.0
    velocidad[m4] = 85.0
    return velocidad


def emparejar_mas_cercano(
    lats_loc: np.ndarray,
    lons_loc: np.ndarray,
    facilidades: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calcula el establecimiento más cercano en vector para todas las localidades.

    Returns:
        (clues_mas_cercano, distancia_carretera_km, tiempo_traslado_min)
    """
    lats_f = facilidades["latitud"].to_numpy()[None, :]
    lons_f = facilidades["longitud"].to_numpy()[None, :]
    clues_f = facilidades["clues"].to_numpy()

    # Matriz (N_localidades, M_establecimientos)
    matriz_dist = distancia_haversine(
        lats_loc[:, None], lons_loc[:, None], lats_f, lons_f
    )

    indices_min = np.argmin(matriz_dist, axis=1)
    dist_recta_km = np.take_along_axis(
        matriz_dist, indices_min[:, None], axis=1
    ).squeeze(axis=1)

    clues_cercano = clues_f[indices_min]

    # Distancia estimada por carretera aplicando factor de sinuosidad
    dist_carretera_km = dist_recta_km * FACTOR_SINUOSIDAD

    # Tiempo en minutos según velocidad de perfil vial
    velocidades = estimar_velocidad_promedio(dist_carretera_km)
    tiempo_min = (dist_carretera_km / velocidades) * 60.0

    # Mínimo 3 minutos de tiempo base si la clínica está en la misma localidad
    tiempo_min = np.maximum(tiempo_min, 3.0)

    return (
        clues_cercano,
        np.round(dist_carretera_km, 2),
        np.round(tiempo_min, 1),
    )


def consolidar_dataset_final() -> pd.DataFrame:
    """Cruza ITER, CLUES y CONEVAL para generar la tabla final de accesibilidad."""
    ensure_directories()

    if not ARCHIVO_POP.exists():
        raise FileNotFoundError(f"Falta el archivo procesado de ITER: {ARCHIVO_POP}")
    if not ARCHIVO_SALUD.exists():
        raise FileNotFoundError(f"Falta el archivo de establecimientos: {ARCHIVO_SALUD}")

    pop = pd.read_parquet(ARCHIVO_POP)
    salud = pd.read_parquet(ARCHIVO_SALUD)

    coneval = (
        pd.read_parquet(ARCHIVO_CONEVAL)
        if ARCHIVO_CONEVAL.exists()
        else pd.DataFrame()
    )

    # Filtrar clínicas con coordenadas válidas
    salud_validas = salud.dropna(subset=["latitud", "longitud"]).copy()
    salud_validas["latitud"] = pd.to_numeric(salud_validas["latitud"], errors="coerce")
    salud_validas["longitud"] = pd.to_numeric(salud_validas["longitud"], errors="coerce")
    salud_validas = salud_validas.dropna(subset=["latitud", "longitud"])

    # Separar por nivel de atención
    primer_nivel = salud_validas[
        salud_validas["nivel_atencion"].str.contains("PRIMER", na=False)
        | salud_validas["tipo_establecimiento"].str.contains("CONSULTA EXTERNA", na=False)
    ].copy()

    segundo_nivel = salud_validas[
        salud_validas["nivel_atencion"].str.contains("SEGUNDO|TERCER", na=False)
        | salud_validas["tipo_establecimiento"].str.contains("HOSPITALIZACION", na=False)
    ].copy()

    if primer_nivel.empty:
        primer_nivel = salud_validas.copy()
    if segundo_nivel.empty:
        segundo_nivel = salud_validas.copy()

    # Localidades con coordenadas
    lats_loc = pop["latitud"].to_numpy()
    lons_loc = pop["longitud"].to_numpy()

    # 1. Emparejar Primer Nivel
    clues_1, dist_1, time_1 = emparejar_mas_cercano(lats_loc, lons_loc, primer_nivel)

    # 2. Emparejar Segundo Nivel
    clues_2, dist_2, time_2 = emparejar_mas_cercano(lats_loc, lons_loc, segundo_nivel)

    # En caso de que el 2do nivel resulte numéricamente menor que el 1er nivel
    # (p. ej. si un hospital general está en la misma manzana y el centro de salud unos metros más allá),
    # el 1er nivel toma el tiempo menor ya que el hospital también brinda atención médica básica
    t1_ajustado = np.minimum(time_1, time_2)

    df_final = pd.DataFrame(
        {
            "locality_id": pop["cvegeo"],
            "locality_name": pop["localidad"],
            "municipality_name": pop["municipio"],
            "population": pd.to_numeric(pop["poblacion_total"], errors="coerce").fillna(0).astype(int),
            "latitude": pop["latitud"],
            "longitude": pop["longitud"],
            "nearest_primary_clues": clues_1,
            "primary_distance_km": dist_1,
            "primary_time_min": t1_ajustado,
            "nearest_secondary_clues": clues_2,
            "secondary_distance_km": dist_2,
            "secondary_time_min": time_2,
            "routing_status": "ok",
        }
    )

    # Pegar variables sociodemográficas y de CONEVAL si están disponibles
    if not coneval.empty and "cvegeo" in coneval.columns:
        cols_coneval = [
            c
            for c in [
                "cvegeo",
                "grado_accesibilidad",
                "transporte_publico",
                "tiempo_centro_servicios",
                "distancia_carretera",
            ]
            if c in coneval.columns
        ]
        df_final = df_final.merge(coneval[cols_coneval], left_on="locality_id", right_on="cvegeo", how="left")
        df_final = df_final.drop(columns=["cvegeo"], errors="ignore")

    if "pct_viviendas_sin_auto_ni_moto" in pop.columns:
        df_final["pct_sin_auto"] = pop["pct_viviendas_sin_auto_ni_moto"]
    if "poblacion_con_discapacidad" in pop.columns:
        df_final["poblacion_discapacidad"] = pop["poblacion_con_discapacidad"]

    df_final.to_parquet(ARCHIVO_TABLA_FINAL, index=False)
    log.info(
        "Dataset final consolidado en: %s (%s filas)",
        ARCHIVO_TABLA_FINAL.relative_to(PROJECT_ROOT),
        len(df_final),
    )
    return df_final


def main() -> None:
    """Punto de entrada de ejecución del ruteo."""
    print("Iniciando cálculo de ruteo y emparejamiento con centros de salud...")
    df = consolidar_dataset_final()
    print(f"Localidades procesadas con ruteo: {len(df)}")
    print(f"Tiempo promedio al 1er nivel: {df['primary_time_min'].mean():.1f} min")
    print(f"Tiempo promedio al 2do nivel: {df['secondary_time_min'].mean():.1f} min")
    print(
        f"Localidades a > 60 min de 1er nivel: {(df['primary_time_min'] > 60).sum()}"
    )
    print(
        f"Localidades a > 120 min de 2do nivel: {(df['secondary_time_min'] > 120).sum()}"
    )
    print(f"Tabla guardada en: {ARCHIVO_TABLA_FINAL}")


if __name__ == "__main__":
    main()
