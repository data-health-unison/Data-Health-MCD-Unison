"""Indicadores de accesibilidad y vulnerabilidad sobre la tabla final.

Responde la pregunta principal del proyecto: ¿dónde se concentran las poblaciones
de Sonora con menor accesibilidad geográfica a servicios de salud?

- ``poblacion_por_rango``: población por rango de tiempo de traslado.
- ``resumen_municipal``: población con acceso comprometido por municipio.
- ``localidades_prioritarias``: localidades con acceso comprometido, por población.
- ``resumen_estatal``: cifras generales y cobertura de rutas SAKBÉ.

Los umbrales salen de ``config/fuentes_health.yaml``. Una localidad tiene
**acceso comprometido** si supera el umbral crítico de 1er o de 2do nivel.

Notas metodológicas:
- Los grupos vulnerables se suman en personas. ITER no publica estas variables en
  localidades confidenciales (muy pequeñas); ``resumen_estatal`` informa qué
  porcentaje de la población tiene el dato.
- La población sin automóvil ni motocicleta se estima como población × porcentaje
  de viviendas sin vehículo (supone tamaño de hogar homogéneo en la localidad).
- Los tiempos pueden ser medidos (SAKBÉ) o estimados; ``routing_status`` y las
  columnas ``*_method`` lo indican.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from health_data.config import Umbrales, cargar_configuracion

NIVELES = {
    "primer": "primary_time_min",
    "segundo": "secondary_time_min",
}

GRUPOS_VULNERABLES = {
    "poblacion_60_y_mas": "60 años y más",
    "poblacion_con_discapacidad": "Con discapacidad",
    "poblacion_sin_afiliacion": "Sin afiliación a servicios de salud",
    "poblacion_lengua_indigena": "Hablante de lengua indígena",
    "poblacion_sin_auto_estimada": "Sin automóvil ni motocicleta (estimada)",
}


def _umbrales(umbrales: Umbrales | None) -> Umbrales:
    return umbrales or cargar_configuracion().umbrales


def umbral_critico(nivel: str, umbrales: Umbrales | None = None) -> float:
    """Umbral crítico en minutos para el nivel de atención."""
    u = _umbrales(umbrales)
    return float(u.tiempo_critico_min if nivel == "primer" else u.tiempo_critico_segundo_nivel_min)


def cortes_por_nivel(nivel: str, umbrales: Umbrales | None = None) -> list[float]:
    """Límites de los rangos de tiempo (minutos) para cada nivel de atención."""
    u = _umbrales(umbrales)
    if nivel == "primer":
        cortes = [0, 30, u.tiempo_critico_min, u.tiempo_muy_critico_min]
    elif nivel == "segundo":
        # 180 min se conserva como corte para distinguir traslados de más de 3 horas
        cortes = [0, 60, 120, 180, u.tiempo_critico_segundo_nivel_min]
    else:
        raise ValueError(f"nivel debe ser uno de {list(NIVELES)}, no {nivel!r}")
    return sorted({float(c) for c in cortes}) + [np.inf]


def _etiquetas(cortes: list[float]) -> list[str]:
    etiquetas = []
    for inf, sup in zip(cortes[:-1], cortes[1:]):
        if inf == 0:
            etiquetas.append(f"≤ {sup:.0f} min")
        elif np.isinf(sup):
            etiquetas.append(f"> {inf:.0f} min")
        else:
            etiquetas.append(f"{inf:.0f}–{sup:.0f} min")
    return etiquetas


def preparar_tabla(tabla: pd.DataFrame) -> pd.DataFrame:
    """Copia de la tabla con tipos numéricos y la población sin vehículo estimada."""
    t = tabla.copy()
    t["population"] = pd.to_numeric(t["population"], errors="coerce").fillna(0)
    for col in (*NIVELES.values(), *GRUPOS_VULNERABLES):
        if col in t.columns:
            t[col] = pd.to_numeric(t[col], errors="coerce")
    if "pct_viviendas_sin_auto_ni_moto" in t.columns:
        pct = pd.to_numeric(t["pct_viviendas_sin_auto_ni_moto"], errors="coerce")
        t["poblacion_sin_auto_estimada"] = (t["population"] * pct / 100).round()
    return t


def _grupos_presentes(t: pd.DataFrame) -> list[str]:
    return [c for c in GRUPOS_VULNERABLES if c in t.columns]


def acceso_comprometido(
    tabla: pd.DataFrame,
    *,
    umbral_primer: float | None = None,
    umbral_segundo: float | None = None,
    umbrales: Umbrales | None = None,
) -> pd.Series:
    """True si la localidad supera el umbral crítico de 1er o de 2do nivel."""
    u1 = umbral_primer if umbral_primer is not None else umbral_critico("primer", umbrales)
    u2 = umbral_segundo if umbral_segundo is not None else umbral_critico("segundo", umbrales)
    t1 = pd.to_numeric(tabla["primary_time_min"], errors="coerce")
    t2 = pd.to_numeric(tabla["secondary_time_min"], errors="coerce")
    return (t1 > u1) | (t2 > u2)


def poblacion_por_rango(
    tabla: pd.DataFrame, nivel: str = "primer", umbrales: Umbrales | None = None
) -> pd.DataFrame:
    """Localidades, población y grupos vulnerables por rango de tiempo de traslado."""
    t = preparar_tabla(tabla)
    cortes = cortes_por_nivel(nivel, umbrales)
    rango = pd.cut(t[NIVELES[nivel]], cortes, labels=_etiquetas(cortes), include_lowest=True)
    grupos = _grupos_presentes(t)

    resultado = (
        t.assign(rango=rango)
        .groupby("rango", observed=False)
        .agg(
            localidades=("population", "size"),
            poblacion=("population", "sum"),
            **{g: (g, "sum") for g in grupos},
        )
    )
    total = resultado["poblacion"].sum()
    resultado.insert(2, "pct_poblacion", 100 * resultado["poblacion"] / total if total else 0.0)
    return resultado.astype({"localidades": int, "poblacion": int, **{g: int for g in grupos}})


def _promedio_ponderado(valores: pd.Series, pesos: pd.Series) -> float:
    mascara = valores.notna()
    if not mascara.any():
        return float("nan")
    if pesos[mascara].sum() <= 0:
        return float(valores[mascara].mean())
    return float(np.average(valores[mascara], weights=pesos[mascara]))


def resumen_municipal(
    tabla: pd.DataFrame,
    *,
    umbral_primer: float | None = None,
    umbral_segundo: float | None = None,
    umbrales: Umbrales | None = None,
) -> pd.DataFrame:
    """Indicadores por municipio, ordenados por población con acceso comprometido.

    Los tiempos promedio se ponderan por población, para que reflejen el tiempo
    que enfrenta una persona típica del municipio y no una localidad típica.
    """
    t = preparar_tabla(tabla)
    u1 = umbral_primer if umbral_primer is not None else umbral_critico("primer", umbrales)
    u2 = umbral_segundo if umbral_segundo is not None else umbral_critico("segundo", umbrales)
    t["_critico_1"] = t["primary_time_min"] > u1
    t["_critico_2"] = t["secondary_time_min"] > u2
    t["_comprometido"] = t["_critico_1"] | t["_critico_2"]
    t["_sakbe"] = t["routing_status"].eq("ok") if "routing_status" in t.columns else False
    grupos = _grupos_presentes(t)

    filas = []
    for municipio, g in t.groupby("municipality_name", sort=False):
        poblacion = g["population"].sum()
        comp = g[g["_comprometido"]]
        fila = {
            "municipio": municipio,
            #Clave de 5 dígitos (entidad + municipio) para cruzar con la cartografía
            "cvegeo": str(g["locality_id"].iloc[0])[:5] if "locality_id" in g.columns else "",
            "localidades": len(g),
            "poblacion": int(poblacion),
            "tiempo_primer_ponderado": _promedio_ponderado(g["primary_time_min"], g["population"]),
            "tiempo_segundo_ponderado": _promedio_ponderado(g["secondary_time_min"], g["population"]),
            "poblacion_primer_critico": int(g.loc[g["_critico_1"], "population"].sum()),
            "poblacion_segundo_critico": int(g.loc[g["_critico_2"], "population"].sum()),
            "localidades_comprometidas": len(comp),
            "poblacion_comprometida": int(comp["population"].sum()),
            **{f"{grupo}_comprometida": int(comp[grupo].sum()) for grupo in grupos},
            "pct_localidades_sakbe": 100 * g["_sakbe"].mean(),
        }
        fila["pct_poblacion_comprometida"] = 100 * fila["poblacion_comprometida"] / poblacion if poblacion else 0.0
        filas.append(fila)

    resultado = pd.DataFrame(filas)
    if resultado.empty:
        return resultado
    return resultado.sort_values(
        ["poblacion_comprometida", "tiempo_segundo_ponderado"], ascending=False
    ).reset_index(drop=True)


def localidades_prioritarias(
    tabla: pd.DataFrame,
    *,
    n: int | None = 20,
    umbral_primer: float | None = None,
    umbral_segundo: float | None = None,
    umbrales: Umbrales | None = None,
) -> pd.DataFrame:
    """Localidades con acceso comprometido, de mayor a menor población."""
    t = preparar_tabla(tabla)
    mascara = acceso_comprometido(
        t, umbral_primer=umbral_primer, umbral_segundo=umbral_segundo, umbrales=umbrales
    )
    columnas = [
        c
        for c in [
            "locality_id",
            "locality_name",
            "municipality_name",
            "population",
            "primary_time_min",
            "primary_method",
            "secondary_time_min",
            "secondary_method",
            "pct_60_y_mas",
            "pct_con_discapacidad",
            "pct_sin_afiliacion",
            "pct_lengua_indigena",
            "pct_viviendas_sin_auto_ni_moto",
            "routing_status",
        ]
        if c in t.columns
    ]
    resultado = t.loc[mascara, columnas].sort_values(
        ["population", "secondary_time_min"], ascending=False
    )
    return resultado.head(n).reset_index(drop=True) if n else resultado.reset_index(drop=True)


def resumen_estatal(
    tabla: pd.DataFrame,
    *,
    umbral_primer: float | None = None,
    umbral_segundo: float | None = None,
    umbrales: Umbrales | None = None,
) -> dict[str, float]:
    """Cifras generales del estado y cobertura de las fuentes."""
    t = preparar_tabla(tabla)
    poblacion = float(t["population"].sum())
    comp = acceso_comprometido(
        t, umbral_primer=umbral_primer, umbral_segundo=umbral_segundo, umbrales=umbrales
    )
    ok = t["routing_status"].eq("ok") if "routing_status" in t.columns else pd.Series(False, index=t.index)
    con_datos = (
        t["poblacion_60_y_mas"].notna()
        if "poblacion_60_y_mas" in t.columns
        else pd.Series(False, index=t.index)
    )

    def pct(mascara: pd.Series) -> float:
        return 100 * float(t.loc[mascara, "population"].sum()) / poblacion if poblacion else 0.0

    return {
        "localidades": int(len(t)),
        "poblacion": int(poblacion),
        "localidades_comprometidas": int(comp.sum()),
        "poblacion_comprometida": int(t.loc[comp, "population"].sum()),
        "pct_poblacion_comprometida": pct(comp),
        "pct_localidades_sakbe": 100 * float(ok.mean()) if len(t) else 0.0,
        "pct_poblacion_sakbe": pct(ok),
        "pct_poblacion_con_datos_vulnerabilidad": pct(con_datos),
    }
