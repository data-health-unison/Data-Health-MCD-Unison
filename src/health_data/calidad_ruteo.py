"""Procedencia y sensibilidad de los tiempos de acceso, sin consultas externas."""

import numpy as np
import pandas as pd

NIVELES = {"primary": ("Primer nivel", 60), "secondary": ("Segundo nivel", 120)}
METODOS = {"sakbe", "coneval", "estimado"}
ESTADOS = {"ok", "parcial", "sin_ruta", "estimado"}


def tiempos_por_nivel(tabla: pd.DataFrame) -> pd.DataFrame:
    campos = ["locality_id", "locality_name", "municipality_name", "population",
              "routing_status", "routing_consulted_at", "tiempo_centro_servicios"]
    partes = []
    for prefijo, (nivel, umbral) in NIVELES.items():
        parte = tabla.reindex(columns=campos).copy()
        parte["nivel"] = nivel
        parte["umbral_min"] = umbral
        metodo = tabla.get(f"{prefijo}_method", pd.Series(index=tabla.index, dtype="string"))
        parte["metodo"] = metodo.where(metodo.isin(METODOS), "sin_dato")
        minutos = pd.to_numeric(tabla.get(f"{prefijo}_time_min", pd.Series(index=tabla.index)),
                                errors="coerce")
        parte["tiempo_min"] = minutos.where(np.isfinite(minutos) & minutos.ge(0))
        parte["motivo"] = parte["routing_status"].map({
            "ok": "Ruta disponible en ambos niveles",
            "parcial": "Ruta disponible en un nivel",
            "sin_ruta": "SAKBÉ no obtuvo ruta",
            "estimado": "Consulta sin confirmar en la tabla",
        }).fillna("Estado sin registrar")
        parte.loc[parte["metodo"].eq("sakbe"), "motivo"] = "Ruta disponible para este nivel"
        parte.loc[parte["tiempo_min"].isna(), "motivo"] = "Tiempo válido no disponible"
        partes.append(parte)
    return pd.concat(partes, ignore_index=True)


def padron_provisional(tiempos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por localidad y nivel con tiempo faltante o sin ruta registrada."""
    revisar = tiempos["metodo"].ne("sakbe") | tiempos["tiempo_min"].isna()
    return tiempos.loc[revisar].sort_values(["population", "locality_id", "nivel"],
                                           ascending=[False, True, True])


def sensibilidad(tiempos: pd.DataFrame, margen_min: int = 15) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mide cambios de clasificación al variar el umbral en ambos sentidos."""
    if not 0 < margen_min < min(umbral for _, umbral in NIVELES.values()):
        raise ValueError("El margen debe ser positivo y menor al umbral de primer nivel")
    datos = tiempos.copy()
    tiempo, umbral = datos["tiempo_min"], datos["umbral_min"]
    datos["con_tiempo"] = tiempo.notna()
    datos["sobre_umbral"] = tiempo.gt(umbral)
    datos["cambia_umbral_menor"] = tiempo.gt(umbral - margen_min) & tiempo.le(umbral)
    datos["cambia_umbral_mayor"] = tiempo.gt(umbral) & tiempo.le(umbral + margen_min)
    cambia = datos["cambia_umbral_menor"] | datos["cambia_umbral_mayor"]
    datos["poblacion_cambia"] = datos["population"].where(cambia, 0)
    datos["distancia_al_umbral_min"] = (tiempo - umbral).abs()
    resumen = datos.groupby(["nivel", "metodo", "municipality_name"], dropna=False).agg(
        localidades=("nivel", "size"),
        con_tiempo=("con_tiempo", "sum"),
        sobre_umbral=("sobre_umbral", "sum"),
        cambia_umbral_menor=("cambia_umbral_menor", "sum"),
        cambia_umbral_mayor=("cambia_umbral_mayor", "sum"),
        poblacion_cambia=("poblacion_cambia", "sum"),
    ).reset_index()
    casos = datos.loc[cambia].sort_values(["population", "distancia_al_umbral_min"],
                                         ascending=[False, True])
    return resumen, casos


def comparar_con_estimacion(tabla: pd.DataFrame, salud: pd.DataFrame) -> pd.DataFrame:
    """Compara el tiempo publicado con una estimación al mismo CLUES."""
    from health_data.processing.ruteo import (
        FACTOR_SINUOSIDAD, TIEMPO_MINIMO_MIN, distancia_haversine, estimar_velocidad_promedio,
    )

    unidades = salud.set_index("clues", verify_integrity=True)
    tiempos = tiempos_por_nivel(tabla)
    comparaciones = []
    for prefijo, perfil in (("primary", "primer"), ("secondary", "segundo")):
        nivel, umbral = NIVELES[prefijo]
        destino = tabla[f"nearest_{prefijo}_clues"]
        distancia = distancia_haversine(
            tabla["latitude"].to_numpy(dtype=float), tabla["longitude"].to_numpy(dtype=float),
            destino.map(unidades["latitud"]).to_numpy(dtype=float),
            destino.map(unidades["longitud"]).to_numpy(dtype=float),
        ) * FACTOR_SINUOSIDAD[perfil]
        velocidad = estimar_velocidad_promedio(distancia, perfil)
        estimacion = np.round(np.maximum(distancia / velocidad * 60, TIEMPO_MINIMO_MIN), 1)
        datos = tiempos.loc[tiempos["nivel"].eq(nivel)].copy()
        datos["estimacion_mismo_clues_min"] = estimacion
        datos = datos.loc[datos["metodo"].isin(["sakbe", "coneval"])
                          & datos["tiempo_min"].notna()
                          & datos["estimacion_mismo_clues_min"].notna()].copy()
        datos["cambia_clasificacion"] = datos["tiempo_min"].gt(umbral).ne(
            datos["estimacion_mismo_clues_min"].gt(umbral)
        )
        datos["poblacion_cambia"] = datos["population"].where(datos["cambia_clasificacion"], 0)
        comparaciones.append(datos)
    return pd.concat(comparaciones, ignore_index=True)
