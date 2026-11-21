"""Vistas de los datos complementarios del proyecto."""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from health_data import config
from health_data.visualization import mapas

TRANSPORTE = "🚌 Transporte y marginación"
URGENCIAS = "🏥 Urgencias"
RED_VIAL = "🛣️ Red vial"


@st.cache_data(show_spinner=False)
def _leer_tabla(ruta: Path, modificacion_ns: int) -> pd.DataFrame:
    return pd.read_parquet(ruta)


def _tabla(nombre: str) -> pd.DataFrame:
    ruta = config.PROCESSED_DATA_DIR / nombre
    if not ruta.is_file():
        return pd.DataFrame()
    return _leer_tabla(ruta, ruta.stat().st_mtime_ns)


def vista_transporte(tabla: pd.DataFrame, umbral: float) -> None:
    st.title("Transporte y marginación")
    transporte = _tabla("inegi-resloc-001_localidades.parquet")
    margen = _tabla("conapo-marg-001_localidades.parquet")
    if transporte.empty or margen.empty:
        st.info("Genere los Parquet de transporte y marginación con el pipeline de datos.")
        return
    st.caption("Fuentes de 2020. ITER, Características de las Localidades de INEGI y CONAPO.")
    if tabla.empty or "secondary_time_min" not in tabla:
        st.info("Genere la tabla de accesibilidad para cruzar las fuentes con los tiempos al hospital.")
        izquierda, derecha = st.columns(2)
        izquierda.bar_chart(transporte["transporte_foraneo"].fillna("Sin dato").value_counts())
        derecha.bar_chart(margen["grado_marginacion"].fillna("Sin dato").value_counts())
        return

    datos = tabla.assign(locality_id=tabla["locality_id"].astype("string"))
    for fuente in (transporte[["cvegeo", "transporte_foraneo", "tiempo_cabecera_min",
                             "frecuencia_salidas_cabecera"]],
                   margen[["cvegeo", "grado_marginacion"]]):
        datos = datos.merge(fuente.assign(cvegeo=fuente["cvegeo"].astype("string")),
                            left_on="locality_id", right_on="cvegeo", how="left",
                            validate="one_to_one").drop(columns="cvegeo")
    datos["estado_transporte"] = datos["transporte_foraneo"].fillna("Sin dato")
    datos["grado"] = datos["grado_marginacion"].astype("string").str.strip().str.upper().fillna("Sin dato")
    datos["hacia_hospital"] = pd.to_numeric(datos["secondary_time_min"], errors="coerce")
    evaluables = datos.dropna(subset=["hacia_hospital"])
    lejos = evaluables[evaluables["hacia_hospital"].gt(umbral)]
    doble = lejos[lejos["estado_transporte"].eq("NO")]
    primera, segunda, tercera = st.columns(3)
    primera.metric("Personas en localidades con doble barrera", f"{doble['population'].sum():,}")
    segunda.metric("Localidades con doble barrera", f"{len(doble):,}")
    tercera.metric("Localidades con grado de marginación", f"{datos['grado_marginacion'].count():,}")
    st.caption(f"Doble barrera significa más de {umbral:g} min al hospital y ausencia de transporte foráneo reportada en RESLOC.")
    if "secondary_method" in datos:
        porcentaje = 100 * datos["secondary_method"].eq("sakbe").mean()
        st.caption(f"Cobertura SAKBÉ en la selección · {porcentaje:.1f} %. Consulte el método de cada localidad en el mapa.")

    movilidad = lejos.groupby("estado_transporte", as_index=False)["population"].sum()
    por_grado = evaluables.assign(
        poblacion_lejos=evaluables["population"].where(evaluables["hacia_hospital"].gt(umbral), 0)
    ).groupby("grado", as_index=False)[["population", "poblacion_lejos"]].sum()
    por_grado["porcentaje"] = 100 * por_grado["poblacion_lejos"] / por_grado["population"].where(
        por_grado["population"].gt(0)
    )
    izquierda, derecha = st.columns(2)
    izquierda.plotly_chart(px.bar(movilidad, x="estado_transporte", y="population",
                                  title=f"Transporte en localidades a más de {umbral:g} min",
                                  labels={"estado_transporte": "Transporte foráneo", "population": "Personas"}),
                           use_container_width=True)
    derecha.plotly_chart(px.bar(por_grado, x="grado", y="porcentaje", hover_data=["population"],
                                title="Población con traslado largo por grado de marginación",
                                category_orders={"grado": ["MUY BAJO", "BAJO", "MEDIO", "ALTO", "MUY ALTO", "Sin dato"]},
                                labels={"grado": "Grado", "porcentaje": "% de personas con tiempo disponible",
                                        "population": "Personas con tiempo disponible"}),
                         use_container_width=True)
    pares = evaluables.dropna(subset=["tiempo_cabecera_min"])
    if not pares.empty:
        figura = px.scatter(
            pares, x="tiempo_cabecera_min", y="hacia_hospital", hover_name="locality_name",
            hover_data=["frecuencia_salidas_cabecera"], opacity=.55,
            title="Tiempo a la cabecera y al hospital",
            labels={"tiempo_cabecera_min": "Minutos en transporte público a la cabecera",
                    "hacia_hospital": "Minutos en automóvil al hospital",
                    "frecuencia_salidas_cabecera": "Frecuencia de salidas"},
        )
        figura.add_hline(y=umbral, line_dash="dash", line_color="#BE4533")
        st.plotly_chart(figura, use_container_width=True)
    if doble.empty:
        st.info("La selección no contiene localidades con ambas barreras.")
        return
    st.plotly_chart(mapas.mapa_localidades(
        doble, columna="hacia_hospital", titulo="Localidades con doble barrera",
        columna_metodo="secondary_method" if "secondary_method" in doble else None,
    ), use_container_width=True)
    viviendas = doble.get("viviendas_sin_auto_ni_moto", pd.Series(dtype=float)).dropna()
    if not viviendas.empty:
        st.caption(f"ITER registra {viviendas.sum():,.0f} viviendas sin automóvil ni motocicleta "
                   f"en {len(viviendas):,} de las {len(doble):,} localidades con doble barrera.")
    columnas = ["locality_name", "municipality_name", "population", "hacia_hospital", "grado"]
    st.dataframe(doble.sort_values("population", ascending=False)[columnas], hide_index=True,
                 use_container_width=True, column_config={
                     "locality_name": "Localidad", "municipality_name": "Municipio", "population": "Personas",
                     "hacia_hospital": st.column_config.NumberColumn("Minutos al hospital", format="%.1f"),
                     "grado": "Marginación",
                 })


def vista_urgencias() -> None:
    st.title("Atención de urgencias")
    datos = _tabla("urgencias_mensuales.parquet")
    if datos.empty:
        st.info("Ejecute la libreta 3.1 de urgencias para generar el resumen mensual del tablero.")
        return
    st.caption("Servicios de Salud de Sonora · Atenciones reportadas de 2018 a 2022. El corte de 2022 cubre seis meses.")
    datos["municipio"] = datos["municipio"].fillna("Sin dato")
    datos["anio"] = datos["periodo"].dt.year
    izquierda, derecha = st.columns(2)
    municipios = izquierda.multiselect("Municipios reportados", sorted(datos["municipio"].unique()))
    anios = derecha.multiselect("Años de reporte", sorted(datos["anio"].unique()))
    seleccion = datos[
        datos["municipio"].isin(municipios or datos["municipio"].unique())
        & datos["anio"].isin(anios or datos["anio"].unique())
    ]
    if seleccion.empty:
        st.info("La combinación seleccionada no tiene reportes de urgencias.")
        return
    primera, segunda, tercera = st.columns(3)
    primera.metric("Urgencias reportadas", f"{seleccion['urgencias'].sum():,}")
    segunda.metric("Establecimientos", f"{seleccion['clues'].nunique():,}")
    tercera.metric("Municipios reportados", f"{seleccion['municipio'].nunique():,}")
    mensual = seleccion.groupby("periodo")["urgencias"].sum().reindex(
        pd.date_range(seleccion["periodo"].min(), seleccion["periodo"].max(), freq="MS")
    ).rename_axis("periodo").reset_index()
    st.plotly_chart(px.line(mensual, x="periodo", y="urgencias", markers=True,
                           title="Atenciones de urgencias por mes",
                           labels={"periodo": "Mes", "urgencias": "Atenciones"}), use_container_width=True)
    unidades = seleccion.groupby(["clues", "establecimiento"], dropna=False, as_index=False)["urgencias"].sum()
    unidades = unidades.sort_values("urgencias", ascending=False)
    st.plotly_chart(px.bar(unidades.head(12).iloc[::-1], x="urgencias", y="clues", orientation="h",
                          hover_data=["establecimiento"], title="Establecimientos con mayor volumen reportado",
                          labels={"clues": "CLUES", "urgencias": "Atenciones",
                                  "establecimiento": "Establecimiento"}), use_container_width=True)
    volumen_municipal = seleccion.groupby("municipio", as_index=False)["urgencias"].sum()
    st.plotly_chart(px.bar(volumen_municipal.sort_values("urgencias"), x="urgencias", y="municipio",
                          orientation="h", title="Atenciones reportadas por municipio",
                          labels={"municipio": "Municipio", "urgencias": "Atenciones"}), use_container_width=True)
    st.dataframe(unidades, hide_index=True, use_container_width=True)


def vista_red_vial() -> None:
    st.title("Red vial y acceso hospitalario")
    datos = _tabla("escenario_vial_localidades.parquet")
    ruta = config.PROCESSED_DATA_DIR / "escenario_vial_trayectos.geojson"
    if datos.empty or not ruta.is_file():
        st.info("Ejecute la libreta 3.2 de red vial para generar las rutas del escenario.")
        return
    municipio = datos["municipio"].iloc[0]
    tramo = datos["tramo_cerrado"].iloc[0]
    st.caption(f"Red Nacional de Caminos 2025 · Municipio piloto {municipio.title().replace('Yecora', 'Yécora')} "
               f"· Cierre simulado del tramo {tramo}.")
    demora = datos["aumento_min"].gt(1e-6)
    primera, segunda, tercera = st.columns(3)
    primera.metric("Localidades con aumento", f"{demora.sum():,}")
    segunda.metric("Localidades sin ruta", f"{(~datos['con_ruta']).sum():,}")
    maximo = datos["aumento_min"].max()
    tercera.metric("Mayor aumento", f"{maximo:.2f} min" if pd.notna(maximo) else "Sin dato")
    st.caption("Los tiempos comparan rutas modeladas entre nodos del recorte regional.")

    geometrias = json.loads(ruta.read_text(encoding="utf-8"))["features"]
    figura = go.Figure()
    colores = {"Ruta base": "#156789", "Ruta tras el cierre": "#237D61", "Tramo cerrado": "#BE4533"}
    for trayecto, color in colores.items():
        x, y = [], []
        for elemento in geometrias:
            if elemento["properties"]["trayecto"] != trayecto:
                continue
            geometria = elemento["geometry"]
            lineas = [geometria["coordinates"]] if geometria["type"] == "LineString" else geometria["coordinates"]
            for linea in lineas:
                x.extend([punto[0] for punto in linea] + [None])
                y.extend([punto[1] for punto in linea] + [None])
        if x:
            figura.add_scatter(x=x, y=y, mode="lines", name=trayecto, line={
                "color": color, "width": 4 if trayecto == "Tramo cerrado" else 2,
                "dash": "dash" if trayecto == "Ruta tras el cierre" else "solid",
            })
        if x and trayecto == "Tramo cerrado" and st.toggle("Acercar al tramo cerrado"):
            lon = next(coordenada for coordenada in x if coordenada is not None)
            lat = next(coordenada for coordenada in y if coordenada is not None)
            figura.update_xaxes(range=[lon - .045, lon + .045])
            figura.update_yaxes(range=[lat - .045, lat + .045])
    figura.update_layout(title="Ruta al hospital y desvío simulado",
                         xaxis_title="Longitud", yaxis_title="Latitud", dragmode="pan")
    figura.update_yaxes(scaleanchor="x", scaleratio=1.13)
    st.plotly_chart(figura, use_container_width=True, config={"scrollZoom": True})
    afectadas = datos.loc[demora | ~datos["con_ruta"]].sort_values(
        ["con_ruta", "population"], ascending=[True, False]
    )
    st.dataframe(afectadas[["locality_name", "population", "antes_min", "despues_min",
                            "aumento_min", "con_ruta"]].round(1), hide_index=True,
                 use_container_width=True, column_config={
                     "locality_name": "Localidad", "population": "Personas", "antes_min": "Base (min)",
                     "despues_min": "Tras el cierre (min)", "aumento_min": "Aumento (min)", "con_ruta": "Con ruta",
                 })
