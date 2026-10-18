"""Módulo de ruteo y emparejamiento con establecimientos de salud de 1er y 2do nivel.

Para cada localidad de Sonora:
1. Identifica el establecimiento operativo de primer nivel (centro de salud) más cercano.
2. Identifica el establecimiento operativo de segundo nivel (hospital) más cercano.
3. Estima distancia y tiempo de traslado considerando factor de sinuosidad vial y velocidad de red carretera.
4. Con la API SAKBÉ de INEGI, mide la ruta real por carretera hacia los
   ``CANDIDATOS_POR_NIVEL`` establecimientos más cercanos en línea recta y conserva
   el de menor tiempo. Donde no hay ruta SAKBÉ se mantiene la estimación del paso 3.

Las consultas a SAKBÉ solo se hacen con ``--sakbe`` (gastan cuota). Sin esa opción,
y desde el pipeline, se usan únicamente las rutas ya guardadas en caché.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

from health_data.config import (
    ARCHIVO_TABLA_FINAL,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    ensure_directories,
)
from health_data.ingestion.sakbe import (
    ARCHIVO_CACHE,
    ClienteSakbe,
    SakbeConexionError,
    SakbeCuotaAgotada,
    SakbeError,
    SakbeNoEnCache,
    SakbeSinRuta,
    SakbeTokenError,
)

log = logging.getLogger(__name__)

ARCHIVO_POP = PROCESSED_DATA_DIR / "inegi-pop-001_localidades.parquet"
ARCHIVO_CONEVAL = PROCESSED_DATA_DIR / "coneval-acc-001_localidades.parquet"
ARCHIVO_SALUD = PROCESSED_DATA_DIR / "salud-001_establecimientos.parquet"

#Factor medio de sinuosidad carretera para el terreno de Sonora (relación red vial / línea recta)
FACTOR_SINUOSIDAD = 1.28

#Establecimientos más cercanos en línea recta que se miden con SAKBÉ por nivel
CANDIDATOS_POR_NIVEL = 2
#Tiempo mínimo de traslado (clínica en la misma localidad)
TIEMPO_MINIMO_MIN = 3.0
#Velocidad urbana cuando origen y destino quedan sobre el mismo tramo carretero
VELOCIDAD_MISMA_VIA_KMH = 35.0

#Variables de ITER que se pasan a la tabla final para el análisis de vulnerabilidad
COLUMNAS_VULNERABILIDAD = [
    "disponibilidad",
    "poblacion_60_y_mas",
    "pct_60_y_mas",
    "poblacion_con_discapacidad",
    "pct_con_discapacidad",
    "poblacion_sin_afiliacion",
    "pct_sin_afiliacion",
    "poblacion_lengua_indigena",
    "pct_lengua_indigena",
    "viviendas_habitadas",
    "viviendas_sin_auto_ni_moto",
    "pct_viviendas_sin_auto_ni_moto",
]

ESTADO_OK = "ok"
ESTADO_SIN_RUTA = "sin_ruta"
ESTADO_PENDIENTE = "pendiente"


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

    #Distancia estimada por carretera aplicando factor de sinuosidad
    dist_carretera_km = dist_recta_km * FACTOR_SINUOSIDAD

    #Tiempo en minutos según velocidad de perfil vial
    velocidades = estimar_velocidad_promedio(dist_carretera_km)
    tiempo_min = (dist_carretera_km / velocidades) * 60.0

    #Mínimo 3 minutos de tiempo base si la clínica está en la misma localidad
    tiempo_min = np.maximum(tiempo_min, TIEMPO_MINIMO_MIN)

    return (
        clues_cercano,
        np.round(dist_carretera_km, 2),
        np.round(tiempo_min, 1),
    )


#--------------------------------------------------------------------------
# Ruteo con SAKBÉ
#--------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultadoRuta:
    """Mejor ruta SAKBÉ de una localidad hacia un nivel de atención."""

    estado: str
    clues: str | None = None
    distancia_km: float = float("nan")
    tiempo_min: float = float("nan")
    consultado_en: str = ""


def candidatos_mas_cercanos(
    lats_loc: np.ndarray,
    lons_loc: np.ndarray,
    facilidades: pd.DataFrame,
    k: int,
) -> np.ndarray:
    """Índices (N, k) de los k establecimientos más cercanos en línea recta, del más cercano al más lejano."""
    matriz = distancia_haversine(
        lats_loc[:, None],
        lons_loc[:, None],
        facilidades["latitud"].to_numpy()[None, :],
        facilidades["longitud"].to_numpy()[None, :],
    )
    k = max(1, min(k, matriz.shape[1]))
    indices = np.argpartition(matriz, k - 1, axis=1)[:, :k]
    orden = np.argsort(np.take_along_axis(matriz, indices, axis=1), axis=1)
    return np.take_along_axis(indices, orden, axis=1)


def _pausar_consultas(cliente: ClienteSakbe, motivo: str) -> None:
    """Deja de consultar la API en esta ejecución; lo restante sale solo de caché."""
    if not cliente.solo_cache:
        log.warning("%s Se continúa solo con rutas en caché.", motivo)
        cliente.solo_cache = True


def mejor_ruta_sakbe(
    cliente: ClienteSakbe,
    lat: float,
    lon: float,
    candidatos: list[tuple[str, float, float]],
) -> ResultadoRuta:
    """Mide con SAKBÉ la ruta hacia cada candidato (clues, lat, lon) y devuelve la más rápida.

    El resultado es ``pendiente`` si algún candidato no pudo consultarse (cuota,
    red o modo solo caché): se completará en una ejecución posterior.
    """
    try:
        origen = cliente.buscar_linea(lat, lon)
    except SakbeSinRuta:
        return ResultadoRuta(ESTADO_SIN_RUTA)
    except SakbeCuotaAgotada as exc:
        _pausar_consultas(cliente, str(exc))
        return ResultadoRuta(ESTADO_PENDIENTE)
    except SakbeConexionError as exc:
        _pausar_consultas(cliente, str(exc))
        return ResultadoRuta(ESTADO_PENDIENTE)
    except SakbeNoEnCache:
        return ResultadoRuta(ESTADO_PENDIENTE)

    mejor: ResultadoRuta | None = None
    pendiente = False
    for clues, lat_f, lon_f in candidatos:
        try:
            destino = cliente.buscar_linea(lat_f, lon_f)
            if destino.id_routing_net == origen.id_routing_net:
                #SAKBÉ no calcula rutas dentro de un mismo tramo: trayecto local
                distancia = float(distancia_haversine(lat, lon, lat_f, lon_f))
                tiempo = distancia / VELOCIDAD_MISMA_VIA_KMH * 60.0
                consultado_en = ""
            else:
                ruta = cliente.calcular_ruta(origen, destino)
                distancia, tiempo, consultado_en = ruta.long_km, ruta.tiempo_min, ruta.consultado_en
        except SakbeSinRuta:
            continue
        except (SakbeCuotaAgotada, SakbeConexionError) as exc:
            _pausar_consultas(cliente, str(exc))
            pendiente = True
            continue
        except SakbeNoEnCache:
            pendiente = True
            continue
        except SakbeTokenError:
            raise
        except SakbeError as exc:
            log.warning("Respuesta inesperada de SAKBÉ hacia %s: %s", clues, exc)
            pendiente = True
            continue

        tiempo = max(tiempo, TIEMPO_MINIMO_MIN)
        if mejor is None or tiempo < mejor.tiempo_min:
            mejor = ResultadoRuta(
                ESTADO_OK,
                clues=clues,
                distancia_km=round(distancia, 2),
                tiempo_min=round(tiempo, 1),
                consultado_en=consultado_en,
            )

    if pendiente:
        return ResultadoRuta(ESTADO_PENDIENTE)
    return mejor or ResultadoRuta(ESTADO_SIN_RUTA)


def rutear_con_sakbe(
    pop: pd.DataFrame,
    niveles: dict[str, pd.DataFrame],
    cliente: ClienteSakbe,
    *,
    k: int = CANDIDATOS_POR_NIVEL,
    max_localidades: int | None = None,
) -> dict[str, list[ResultadoRuta]]:
    """Rutas SAKBÉ por nivel, alineadas con las filas de ``pop``.

    Las localidades se recorren de mayor a menor población, para que con cuota
    parcial queden cubiertas primero las que concentran más habitantes.
    """
    lats = pop["latitud"].to_numpy(dtype=float)
    lons = pop["longitud"].to_numpy(dtype=float)
    poblacion = pd.to_numeric(pop["poblacion_total"], errors="coerce").fillna(0).to_numpy()
    orden = np.argsort(-poblacion, kind="stable")
    if max_localidades is not None:
        orden = orden[:max_localidades]

    candidatos_por_nivel = {}
    for nivel, fac in niveles.items():
        indices = candidatos_mas_cercanos(lats, lons, fac, k)
        tabla = list(zip(fac["clues"], fac["latitud"].astype(float), fac["longitud"].astype(float)))
        candidatos_por_nivel[nivel] = (indices, tabla)

    resultados = {nivel: [ResultadoRuta(ESTADO_PENDIENTE)] * len(pop) for nivel in niveles}
    for n, i in enumerate(orden, start=1):
        for nivel, (indices, tabla) in candidatos_por_nivel.items():
            candidatos = [tabla[j] for j in indices[i]]
            resultados[nivel][i] = mejor_ruta_sakbe(cliente, lats[i], lons[i], candidatos)
        if n % 250 == 0 and not cliente.solo_cache:
            log.info(
                "SAKBÉ: %d/%d localidades · %d consultas en esta ejecución · %d restantes hoy",
                n, len(orden), cliente.consultas_sesion, cliente.consultas_restantes(),
            )
    return resultados


def _aplicar_rutas(
    clues: np.ndarray,
    distancia: np.ndarray,
    tiempo: np.ndarray,
    resultados: list[ResultadoRuta],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sustituye la estimación por la ruta SAKBÉ donde existe. Devuelve también el método."""
    clues = clues.astype(object).copy()
    distancia = distancia.astype(float).copy()
    tiempo = tiempo.astype(float).copy()
    metodo = np.full(len(resultados), "estimado", dtype=object)
    for i, r in enumerate(resultados):
        if r.estado == ESTADO_OK:
            clues[i], distancia[i], tiempo[i], metodo[i] = r.clues, r.distancia_km, r.tiempo_min, "sakbe"
    return clues, distancia, tiempo, metodo


def estado_ruteo(r1: list[ResultadoRuta], r2: list[ResultadoRuta]) -> np.ndarray:
    """ok: ambos niveles por SAKBÉ · parcial: uno · sin_ruta: SAKBÉ no halló ruta · estimado: sin consultar."""
    estados = []
    for a, b in zip(r1, r2):
        ok = (a.estado == ESTADO_OK) + (b.estado == ESTADO_OK)
        if ok == 2:
            estados.append("ok")
        elif ok == 1:
            estados.append("parcial")
        elif ESTADO_SIN_RUTA in (a.estado, b.estado):
            estados.append("sin_ruta")
        else:
            estados.append("estimado")
    return np.array(estados, dtype=object)


def consolidar_dataset_final(
    cliente: ClienteSakbe | None = None,
    *,
    candidatos: int = CANDIDATOS_POR_NIVEL,
    max_localidades: int | None = None,
) -> pd.DataFrame:
    """Cruza ITER, CLUES y CONEVAL para generar la tabla final de accesibilidad.

    Con ``cliente`` se usan rutas SAKBÉ donde estén disponibles; el resto de las
    localidades conserva la estimación por línea recta y sinuosidad.
    """
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

    #Filtrar clínicas con coordenadas válidas
    salud_validas = salud.dropna(subset=["latitud", "longitud"]).copy()
    salud_validas["latitud"] = pd.to_numeric(salud_validas["latitud"], errors="coerce")
    salud_validas["longitud"] = pd.to_numeric(salud_validas["longitud"], errors="coerce")
    salud_validas = salud_validas.dropna(subset=["latitud", "longitud"])

    #Separar por nivel de atención
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

    #Localidades con coordenadas
    lats_loc = pop["latitud"].to_numpy()
    lons_loc = pop["longitud"].to_numpy()

    #Emparejar Primer Nivel
    clues_1, dist_1, time_1 = emparejar_mas_cercano(lats_loc, lons_loc, primer_nivel)

    #Emparejar Segundo Nivel
    clues_2, dist_2, time_2 = emparejar_mas_cercano(lats_loc, lons_loc, segundo_nivel)

    #Sustituir por rutas reales de SAKBÉ donde estén disponibles
    metodo_1 = metodo_2 = np.full(len(pop), "estimado", dtype=object)
    estado = np.full(len(pop), "estimado", dtype=object)
    consultado_en = np.full(len(pop), "", dtype=object)
    pendientes = len(pop)
    if cliente is not None:
        rutas = rutear_con_sakbe(
            pop,
            {"primer": primer_nivel, "segundo": segundo_nivel},
            cliente,
            k=candidatos,
            max_localidades=max_localidades,
        )
        clues_1, dist_1, time_1, metodo_1 = _aplicar_rutas(clues_1, dist_1, time_1, rutas["primer"])
        clues_2, dist_2, time_2, metodo_2 = _aplicar_rutas(clues_2, dist_2, time_2, rutas["segundo"])
        estado = estado_ruteo(rutas["primer"], rutas["segundo"])
        consultado_en = np.array(
            [max(a.consultado_en, b.consultado_en) for a, b in zip(rutas["primer"], rutas["segundo"])],
            dtype=object,
        )
        pendientes = sum(
            ESTADO_PENDIENTE in (a.estado, b.estado)
            for a, b in zip(rutas["primer"], rutas["segundo"])
        )

    #En caso de que el 2do nivel resulte numéricamente menor que el 1er nivel
    #(p. ej. si un hospital general está en la misma manzana y el centro de salud unos metros más allá),
    #el 1er nivel toma el tiempo menor ya que el hospital también brinda atención médica básica
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
            "primary_method": metodo_1,
            "nearest_secondary_clues": clues_2,
            "secondary_distance_km": dist_2,
            "secondary_time_min": time_2,
            "secondary_method": metodo_2,
            "routing_status": estado,
            "routing_consulted_at": consultado_en,
        }
    )

    #Variables de vulnerabilidad de ITER (antes del merge para conservar la alineación por fila).
    #En localidades confidenciales de ITER vienen vacías.
    for col in COLUMNAS_VULNERABILIDAD:
        if col in pop.columns:
            df_final[col] = pop[col].to_numpy()

    #Pegar variables de CONEVAL si están disponibles
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

    #Nombres anteriores, conservados por compatibilidad
    if "pct_viviendas_sin_auto_ni_moto" in df_final.columns:
        df_final["pct_sin_auto"] = df_final["pct_viviendas_sin_auto_ni_moto"]
    if "poblacion_con_discapacidad" in df_final.columns:
        df_final["poblacion_discapacidad"] = df_final["poblacion_con_discapacidad"]

    df_final.to_parquet(ARCHIVO_TABLA_FINAL, index=False)
    #Localidades a las que aún les falta consultar SAKBÉ en algún nivel
    df_final.attrs["localidades_pendientes"] = int(pendientes)
    log.info(
        "Dataset final consolidado en: %s (%s filas)",
        ARCHIVO_TABLA_FINAL.relative_to(PROJECT_ROOT),
        len(df_final),
    )
    return df_final


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de ejecución del ruteo.

    Desde el pipeline se llama sin argumentos: solo usa rutas SAKBÉ en caché.
    """
    parser = argparse.ArgumentParser(description="Ruteo de localidades a establecimientos de salud.")
    parser.add_argument(
        "--sakbe",
        action="store_true",
        help="Consulta la API SAKBÉ para las rutas que falten (gasta cuota; se puede reanudar).",
    )
    parser.add_argument(
        "--candidatos",
        type=int,
        default=CANDIDATOS_POR_NIVEL,
        help=f"Establecimientos más cercanos a medir por nivel (por omisión {CANDIDATOS_POR_NIVEL}).",
    )
    parser.add_argument(
        "--max-localidades",
        type=int,
        default=None,
        help="Limita el número de localidades a rutear (las de mayor población primero).",
    )
    args = parser.parse_args(argv if argv is not None else [])
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cliente: ClienteSakbe | None = None
    if args.sakbe:
        try:
            cliente = ClienteSakbe()
        except SakbeTokenError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(
            f"Consultando SAKBÉ con {cliente.num_tokens} tokens "
            f"({cliente.consultas_restantes()} consultas disponibles hoy)..."
        )
    elif ARCHIVO_CACHE.exists():
        cliente = ClienteSakbe(solo_cache=True)
        print("Usando rutas SAKBÉ en caché (sin consultar la API)...")

    print("Iniciando cálculo de ruteo y emparejamiento con centros de salud...")
    try:
        df = consolidar_dataset_final(
            cliente, candidatos=args.candidatos, max_localidades=args.max_localidades
        )
    finally:
        if cliente is not None:
            cliente.cerrar()

    print(f"Localidades procesadas con ruteo: {len(df)}")
    for estado, n in df["routing_status"].value_counts().items():
        print(f"  {estado}: {n:,} localidades")
    if cliente is not None and args.sakbe:
        print(f"Consultas a SAKBÉ en esta ejecución: {cliente.consultas_sesion}")
        pendientes = df.attrs.get("localidades_pendientes", 0)
        if pendientes:
            print(
                f"Quedan {pendientes:,} localidades por completar; vuelva a ejecutar "
                f"`make rutas` (al agotarse la cuota, al día siguiente)."
            )
    print(f"Tiempo promedio al 1er nivel: {df['primary_time_min'].mean():.1f} min")
    print(f"Tiempo promedio al 2do nivel: {df['secondary_time_min'].mean():.1f} min")
    print(
        f"Localidades a > 60 min de 1er nivel: {(df['primary_time_min'] > 60).sum()}"
    )
    print(
        f"Localidades a > 120 min de 2do nivel: {(df['secondary_time_min'] > 120).sum()}"
    )
    print(f"Tabla guardada en: {ARCHIVO_TABLA_FINAL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
