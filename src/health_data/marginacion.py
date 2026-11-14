"""Análisis experimental: marginación (CONAPO-MARG-001) y accesibilidad a servicios de salud.

Pregunta: ¿una localidad con acceso comprometido es más vulnerable si además tiene
marginación alta? Se cruza la tabla final con el índice de marginación por localidad 2020.

- ``unir_marginacion``: agrega el grado y el índice normalizado a la tabla final.
- ``acceso_por_grado``: acceso comprometido por grado de marginación.
- ``clasificar_prioridad``: acceso comprometido × marginación alta, en cuatro grupos.
- ``resumen_prioridad`` y ``localidades_doble_carga``: tamaño y lista de cada grupo.

Notas metodológicas:
- CONAPO solo calcula el índice de localidades con 3 viviendas habitadas o más. A las de
  1 y 2 viviendas se les asigna el agregado de su municipio (``marginacion_origen`` =
  ``agregado_municipal``), que describe al conjunto, no a cada localidad.
- Método DP2: el índice normalizado va de 0 a 1 y un valor MAYOR es MENOR marginación.
  ``marginacion_norm`` lo invierte (1 - IMN) para que mayor sea más marginación.
- Ambas fuentes vienen del Censo 2020; la marginación no cambia con el ruteo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from health_data.analisis import (
    GRUPOS_VULNERABLES,
    _promedio_ponderado,
    acceso_comprometido,
    preparar_tabla,
)
from health_data.config import Umbrales

GRADOS = ["MUY BAJO", "BAJO", "MEDIO", "ALTO", "MUY ALTO"]
GRADOS_ALTOS = ("ALTO", "MUY ALTO")

ORIGEN_LOCALIDAD = "localidad"
ORIGEN_AGREGADO = "agregado_municipal"

PRIORIDADES = [
    "1. Acceso comprometido y marginación alta",
    "2. Acceso comprometido, marginación media o baja",
    "3. Marginación alta, acceso adecuado",
    "4. Sin alerta",
]


def unir_marginacion(
    tabla: pd.DataFrame, localidades: pd.DataFrame, agregados: pd.DataFrame
) -> pd.DataFrame:
    """Tabla final con grado_marginacion, indice_marginacion_norm, marginacion_norm y su origen.

    Primero se busca la localidad por cvegeo; si CONAPO no la calcula (1 o 2 viviendas),
    se usa el agregado de su municipio.
    """
    t = tabla.copy()
    clave = t["locality_id"].astype("string")
    municipio = clave.str[2:5]
    cols = ["grado_marginacion", "indice_marginacion_norm"]

    por_loc = localidades.set_index(localidades["cvegeo"].astype("string"))[cols]
    por_mun = agregados.set_index(agregados["cve_mun"].astype("string"))[cols]
    propio = por_loc.reindex(clave.to_numpy())
    respaldo = por_mun.reindex(municipio.to_numpy())
    tiene_propio = propio["indice_marginacion_norm"].notna().to_numpy()
    tiene_respaldo = respaldo["indice_marginacion_norm"].notna().to_numpy()

    # Por posición: los índices de propio (cvegeo) y respaldo (municipio) no coinciden.
    grado = np.where(
        tiene_propio,
        propio["grado_marginacion"].astype(object).to_numpy(),
        respaldo["grado_marginacion"].astype(object).to_numpy(),
    )
    t["grado_marginacion"] = pd.Categorical(grado, categories=GRADOS, ordered=True)
    t["indice_marginacion_norm"] = np.where(
        tiene_propio,
        propio["indice_marginacion_norm"].to_numpy(dtype=float),
        respaldo["indice_marginacion_norm"].to_numpy(dtype=float),
    )
    t["marginacion_norm"] = 1 - t["indice_marginacion_norm"]
    origen = pd.Series(pd.NA, index=t.index, dtype="string")
    origen[tiene_respaldo & ~tiene_propio] = ORIGEN_AGREGADO
    origen[tiene_propio] = ORIGEN_LOCALIDAD
    t["marginacion_origen"] = origen
    return t


def _comprometido(t: pd.DataFrame, umbrales: Umbrales | None) -> pd.Series:
    return acceso_comprometido(t, umbrales=umbrales)


def acceso_por_grado(
    tabla: pd.DataFrame, *, solo_indice_propio: bool = True, umbrales: Umbrales | None = None
) -> pd.DataFrame:
    """Localidades y población con acceso comprometido en cada grado de marginación.

    Con ``solo_indice_propio`` se descartan las localidades con el agregado municipal,
    para comparar solo valores medidos en la propia localidad.
    """
    t = preparar_tabla(tabla)
    if solo_indice_propio:
        t = t[t["marginacion_origen"].eq(ORIGEN_LOCALIDAD).fillna(False)]
    t = t.assign(comp=_comprometido(t, umbrales))
    t["pob_comp"] = t["population"].where(t["comp"], 0)
    grupos = t.groupby("grado_marginacion", observed=False)
    resultado = grupos.agg(
        localidades=("population", "size"),
        poblacion=("population", "sum"),
        localidades_comprometidas=("comp", "sum"),
        poblacion_comprometida=("pob_comp", "sum"),
    )
    resultado["pct_localidades_comprometidas"] = (
        100 * resultado["localidades_comprometidas"] / resultado["localidades"].where(resultado["localidades"] > 0)
    )
    resultado["pct_poblacion_comprometida"] = (
        100 * resultado["poblacion_comprometida"] / resultado["poblacion"].where(resultado["poblacion"] > 0)
    )
    resultado["tiempo_segundo_ponderado"] = grupos.apply(
        lambda g: _promedio_ponderado(g["secondary_time_min"], g["population"]), include_groups=False
    )
    return resultado.astype(
        {c: int for c in ["localidades", "poblacion", "localidades_comprometidas", "poblacion_comprometida"]}
    )


def clasificar_prioridad(
    tabla: pd.DataFrame,
    *,
    grados_altos: tuple[str, ...] = GRADOS_ALTOS,
    umbrales: Umbrales | None = None,
) -> pd.Categorical:
    """Grupo de prioridad de cada localidad: acceso comprometido × marginación alta.

    Una localidad sin dato de marginación cuenta como marginación no alta.
    """
    comp = _comprometido(tabla, umbrales).to_numpy()
    alta = tabla["grado_marginacion"].isin(grados_altos).to_numpy()
    etiquetas = pd.Series(PRIORIDADES[3], index=tabla.index)
    etiquetas[~comp & alta] = PRIORIDADES[2]
    etiquetas[comp & ~alta] = PRIORIDADES[1]
    etiquetas[comp & alta] = PRIORIDADES[0]
    return pd.Categorical(etiquetas, categories=PRIORIDADES, ordered=True)


def resumen_prioridad(
    tabla: pd.DataFrame,
    *,
    grados_altos: tuple[str, ...] = GRADOS_ALTOS,
    umbrales: Umbrales | None = None,
) -> pd.DataFrame:
    """Localidades, población y grupos vulnerables en cada grupo de prioridad."""
    t = preparar_tabla(tabla)
    t["prioridad"] = clasificar_prioridad(t, grados_altos=grados_altos, umbrales=umbrales)
    t["indice_propio"] = t["marginacion_origen"].eq(ORIGEN_LOCALIDAD).fillna(False)
    grupos = [g for g in GRUPOS_VULNERABLES if g in t.columns]
    resultado = t.groupby("prioridad", observed=False).agg(
        localidades=("population", "size"),
        localidades_indice_propio=("indice_propio", "sum"),
        poblacion=("population", "sum"),
        **{g: (g, "sum") for g in grupos},
    )
    total = resultado["poblacion"].sum()
    resultado.insert(3, "pct_poblacion", 100 * resultado["poblacion"] / total if total else 0.0)
    return resultado.astype({"localidades": int, "localidades_indice_propio": int, "poblacion": int})


def localidades_doble_carga(
    tabla: pd.DataFrame,
    *,
    grados_altos: tuple[str, ...] = GRADOS_ALTOS,
    umbrales: Umbrales | None = None,
    n: int | None = None,
) -> pd.DataFrame:
    """Localidades con acceso comprometido y marginación alta, de mayor a menor población."""
    t = preparar_tabla(tabla)
    prioridad = clasificar_prioridad(t, grados_altos=grados_altos, umbrales=umbrales)
    columnas = [
        "locality_id",
        "locality_name",
        "municipality_name",
        "population",
        "primary_time_min",
        "secondary_time_min",
        "grado_marginacion",
        "marginacion_norm",
        "marginacion_origen",
    ]
    resultado = (
        t.loc[prioridad == PRIORIDADES[0], columnas]
        .sort_values(["population", "secondary_time_min"], ascending=[False, False])
        .reset_index(drop=True)
    )
    return resultado.head(n) if n else resultado
