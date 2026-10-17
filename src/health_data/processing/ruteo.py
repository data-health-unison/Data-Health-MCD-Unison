"""Ruteo y emparejamiento con establecimientos de salud de 1er y 2do nivel.

Para cada localidad de Sonora:
1. Identifica el establecimiento operativo de primer nivel (centro de salud) más cercano.
2. Identifica el establecimiento operativo de segundo nivel (hospital) más cercano.
3. Calcula rutas con SAKBÉ o, en modo estimado explícito, aproxima distancia y tiempo.
"""

from __future__ import annotations

import logging
from typing import Protocol

import numpy as np
import pandas as pd

from health_data.config import (
    ARCHIVO_CACHE_SAKBE,
    ARCHIVO_TABLA_FINAL,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    cargar_configuracion,
    ensure_directories,
)
from health_data.processing.sakbe import (
    RouteResult,
    SakbeClient,
    SakbeError,
    SakbeFatalError,
    SakbeQuotaExceeded,
    crear_cliente_desde_entorno,
)

log = logging.getLogger(__name__)

ARCHIVO_POP = PROCESSED_DATA_DIR / "inegi-pop-001_localidades.parquet"
ARCHIVO_CONEVAL = PROCESSED_DATA_DIR / "coneval-acc-001_localidades.parquet"
ARCHIVO_SALUD = PROCESSED_DATA_DIR / "salud-001_establecimientos.parquet"

# Factor medio de sinuosidad carretera para el terreno de Sonora (relación red vial / línea recta)
FACTOR_SINUOSIDAD = 1.28
LATITUD_MIN_SONORA = 25.5
LATITUD_MAX_SONORA = 33.0
LONGITUD_MIN_SONORA = -116.0
LONGITUD_MAX_SONORA = -108.0


def _coordenadas_validas_sonora(
    latitud: float | np.ndarray, longitud: float | np.ndarray
) -> bool | np.bool_ | np.ndarray:
    return (
        np.isfinite(latitud)
        & np.isfinite(longitud)
        & (latitud >= LATITUD_MIN_SONORA)
        & (latitud <= LATITUD_MAX_SONORA)
        & (longitud >= LONGITUD_MIN_SONORA)
        & (longitud <= LONGITUD_MAX_SONORA)
    )


class ClienteRuteo(Protocol):
    """Contrato mínimo requerido por el cálculo de rutas."""

    def calcular_ruta(
        self, origen: tuple[float, float], destino: tuple[float, float]
    ) -> RouteResult | None: ...


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
    velocidad = np.full_like(distancia_carretera_km, np.nan, dtype=float)
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
    """Estima el candidato más cercano por línea recta y sus tiempos aproximados.

    Returns:
        (clues_candidato, distancia_estimada_km, tiempo_estimado_min)
    """
    indices_min, dist_recta_km = _candidatos_geodesicos(
        lats_loc, lons_loc, facilidades
    )
    dist_carretera_km = dist_recta_km * FACTOR_SINUOSIDAD
    velocidades = estimar_velocidad_promedio(dist_carretera_km)
    tiempo_min = (dist_carretera_km / velocidades) * 60.0
    tiempo_min = np.maximum(tiempo_min, 3.0)
    clues = facilidades["clues"].to_numpy()
    clues_cercano = np.full(len(lats_loc), None, dtype=object)
    validas = indices_min >= 0
    clues_cercano[validas] = clues[indices_min[validas]]
    return (
        clues_cercano,
        np.round(dist_carretera_km, 2),
        np.round(tiempo_min, 1),
    )


def _candidatos_geodesicos(
    lats_loc: np.ndarray,
    lons_loc: np.ndarray,
    facilidades: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Busca el candidato por distancia geodésica, sin afirmar que sea ruta vial."""
    if facilidades.empty:
        raise ValueError("No hay establecimientos válidos para el nivel solicitado.")
    lats_fac_todas = facilidades["latitud"].to_numpy(dtype=float)
    lons_fac_todas = facilidades["longitud"].to_numpy(dtype=float)
    facilidades_validas = _coordenadas_validas_sonora(
        lats_fac_todas, lons_fac_todas
    )
    indices_facilidades = np.flatnonzero(facilidades_validas)
    if len(indices_facilidades) == 0:
        raise ValueError("No hay establecimientos con coordenadas válidas en Sonora.")
    lats_fac = lats_fac_todas[facilidades_validas]
    lons_fac = lons_fac_todas[facilidades_validas]
    indices = np.full(len(lats_loc), -1, dtype=int)
    distancias = np.full(len(lats_loc), np.nan, dtype=float)
    for i, (lat, lon) in enumerate(zip(lats_loc, lons_loc, strict=True)):
        if not _coordenadas_validas_sonora(lat, lon):
            continue
        dist = distancia_haversine(lat, lon, lats_fac, lons_fac)
        if not np.isfinite(dist).any():
            continue
        indice_valido = int(np.nanargmin(dist))
        indices[i] = indices_facilidades[indice_valido]
        distancias[i] = float(dist[indice_valido])
    return indices, distancias


def _establecimientos_por_nivel(salud: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Selecciona únicamente registros CLUES explícitos de cada nivel."""
    salud_validas = salud.copy()
    salud_validas["latitud"] = pd.to_numeric(salud_validas["latitud"], errors="coerce")
    salud_validas["longitud"] = pd.to_numeric(salud_validas["longitud"], errors="coerce")
    salud_validas = salud_validas.dropna(subset=["clues"])
    coordenadas_validas = _coordenadas_validas_sonora(
        salud_validas["latitud"].to_numpy(dtype=float),
        salud_validas["longitud"].to_numpy(dtype=float),
    )
    salud_validas = salud_validas.loc[coordenadas_validas]
    niveles = salud_validas["nivel_atencion"].astype("string").str.strip().str.upper()
    primer_nivel = salud_validas[niveles.eq("PRIMER NIVEL")].reset_index(drop=True)
    segundo_nivel = salud_validas[niveles.eq("SEGUNDO NIVEL")].reset_index(drop=True)
    if primer_nivel.empty:
        raise ValueError("CLUES no contiene establecimientos válidos de primer nivel.")
    if segundo_nivel.empty:
        raise ValueError("CLUES no contiene establecimientos válidos de segundo nivel.")
    return primer_nivel, segundo_nivel


def _rutas_sakbe(
    pop: pd.DataFrame,
    primer_nivel: pd.DataFrame,
    segundo_nivel: pd.DataFrame,
    candidatos_1: np.ndarray,
    candidatos_2: np.ndarray,
    cliente: ClienteRuteo,
) -> pd.DataFrame:
    """Calcula las dos rutas de cada localidad y conserva estados independientes."""
    n = len(pop)
    dist_1 = np.full(n, np.nan)
    tiempo_1 = np.full(n, np.nan)
    dist_2 = np.full(n, np.nan)
    tiempo_2 = np.full(n, np.nan)
    estado_1 = np.full(n, "pending", dtype=object)
    estado_2 = np.full(n, "pending", dtype=object)
    agotada = False

    for i, fila in enumerate(pop.itertuples(index=False)):
        lat = float(fila.latitud)
        lon = float(fila.longitud)
        if not _coordenadas_validas_sonora(lat, lon):
            estado_1[i] = estado_2[i] = "invalid_coordinates"
            continue
        for establecimientos, candidatos, distancias, tiempos, estados in (
            (primer_nivel, candidatos_1, dist_1, tiempo_1, estado_1),
            (segundo_nivel, candidatos_2, dist_2, tiempo_2, estado_2),
        ):
            if agotada:
                estados[i] = "quota_exceeded"
                continue
            indice = int(candidatos[i])
            if indice < 0:
                estados[i] = "invalid_coordinates"
                continue
            destino = establecimientos.iloc[indice]
            try:
                resultado = cliente.calcular_ruta(
                    (lat, lon),
                    (float(destino["latitud"]), float(destino["longitud"])),
                )
            except SakbeQuotaExceeded:
                agotada = True
                estados[i] = "quota_exceeded"
                log.warning(
                    "Cuota diaria SAKBÉ alcanzada; se conserva el avance y "
                    "las rutas restantes quedan pendientes."
                )
                continue
            except SakbeFatalError:
                raise
            except SakbeError as exc:
                estados[i] = "api_error"
                log.error("Falló ruteo SAKBÉ para localidad %s: %s", fila.cvegeo, exc)
                continue
            if resultado is None:
                estados[i] = "no_route"
                continue
            distancias[i] = resultado.distance_km
            tiempos[i] = resultado.time_min
            estados[i] = "sakbe_ok"

    estados_globales = []
    for p, s in zip(estado_1, estado_2, strict=True):
        if p == s == "sakbe_ok":
            estados_globales.append("sakbe_ok")
        elif p == "sakbe_ok" or s == "sakbe_ok":
            estados_globales.append("partial")
        elif "quota_exceeded" in (p, s):
            estados_globales.append("quota_exceeded")
        elif "api_error" in (p, s):
            estados_globales.append("api_error")
        else:
            estados_globales.append("no_route")
    return pd.DataFrame(
        {
            "primary_distance_km": dist_1,
            "primary_time_min": tiempo_1,
            "primary_routing_status": estado_1,
            "secondary_distance_km": dist_2,
            "secondary_time_min": tiempo_2,
            "secondary_routing_status": estado_2,
            "routing_status": estados_globales,
        }
    )


def consolidar_dataset_final(
    *,
    metodo: str = "estimated",
    cliente_sakbe: SakbeClient | None = None,
) -> pd.DataFrame:
    """Cruza ITER, CLUES y CONEVAL para generar la tabla final de accesibilidad."""
    ensure_directories()
    if metodo not in {"estimated", "sakbe"}:
        raise ValueError("El método de ruteo debe ser 'estimated' o 'sakbe'.")

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

    pop = pop.copy()
    pop["latitud"] = pd.to_numeric(pop["latitud"], errors="coerce")
    pop["longitud"] = pd.to_numeric(pop["longitud"], errors="coerce")
    primer_nivel, segundo_nivel = _establecimientos_por_nivel(salud)
    lats_loc = pop["latitud"].to_numpy(dtype=float)
    lons_loc = pop["longitud"].to_numpy(dtype=float)
    clues_1, dist_1, time_1 = emparejar_mas_cercano(
        lats_loc, lons_loc, primer_nivel
    )
    clues_2, dist_2, time_2 = emparejar_mas_cercano(
        lats_loc, lons_loc, segundo_nivel
    )
    estado_1 = np.where(np.isfinite(time_1), "estimated", "invalid_coordinates")
    estado_2 = np.where(np.isfinite(time_2), "estimated", "invalid_coordinates")
    estado_global = np.where(
        (estado_1 == "estimated") & (estado_2 == "estimated"),
        "estimated",
        "no_route",
    )

    if metodo == "sakbe":
        cfg = cargar_configuracion()
        fuente = cfg.fuente("INEGI-ROUTE-001")
        propio_cliente = cliente_sakbe is None
        cliente = cliente_sakbe or crear_cliente_desde_entorno(
            ARCHIVO_CACHE_SAKBE,
            fuente.limite_diario or cfg.umbrales.sakbe_limite_diario,
            fuente.api_base.rstrip("/"),
            fuente.token_env,
        )
        try:
            rutas = _rutas_sakbe(
                pop,
                primer_nivel,
                segundo_nivel,
                _candidatos_geodesicos(lats_loc, lons_loc, primer_nivel)[0],
                _candidatos_geodesicos(lats_loc, lons_loc, segundo_nivel)[0],
                cliente,
            )
        finally:
            if propio_cliente:
                cliente.cerrar()
        dist_1 = rutas["primary_distance_km"].to_numpy()
        time_1 = rutas["primary_time_min"].to_numpy()
        estado_1 = rutas["primary_routing_status"].to_numpy()
        dist_2 = rutas["secondary_distance_km"].to_numpy()
        time_2 = rutas["secondary_time_min"].to_numpy()
        estado_2 = rutas["secondary_routing_status"].to_numpy()
        estado_global = rutas["routing_status"].to_numpy()

    df_final = pd.DataFrame(
        {
            "locality_id": pop["cvegeo"],
            "locality_name": pop["localidad"],
            "municipality_name": pop["municipio"],
            "population": pd.to_numeric(pop["poblacion_total"], errors="coerce").fillna(0).astype(int),
            "latitude": pop["latitud"],
            "longitude": pop["longitud"],
            "primary_candidate_clues": clues_1,
            "primary_distance_km": dist_1,
            "primary_time_min": time_1,
            "primary_routing_status": estado_1,
            "secondary_candidate_clues": clues_2,
            "secondary_distance_km": dist_2,
            "secondary_time_min": time_2,
            "secondary_routing_status": estado_2,
            "routing_method": metodo,
            "facility_selection_method": "nearest_geodesic",
            "routing_status": estado_global,
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


def main(metodo: str = "estimated") -> None:
    """Punto de entrada de ejecución del ruteo."""
    print(f"Iniciando accesibilidad a centros de salud (método: {metodo})...")
    df = consolidar_dataset_final(metodo=metodo)
    print(f"Localidades procesadas: {len(df)}")
    print(f"Método registrado: {metodo}")
    print(
        "Tiempo promedio al 1er nivel: "
        f"{df['primary_time_min'].mean():.1f} min"
    )
    print(
        "Tiempo promedio al 2do nivel: "
        f"{df['secondary_time_min'].mean():.1f} min"
    )
    print(
        "Localidades a > 60 min de 1er nivel: "
        f"{int(df['primary_time_min'].gt(60).sum())}"
    )
    print(
        "Localidades a > 120 min de 2do nivel: "
        f"{int(df['secondary_time_min'].gt(120).sum())}"
    )
    print(f"Tabla guardada en: {ARCHIVO_TABLA_FINAL}")


if __name__ == "__main__":
    main()
