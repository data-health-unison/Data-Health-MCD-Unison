"""Constructores de mapas y figuras Plotly para el tablero de salud.

Permite graficar coropléticos municipales de Sonora sobre GeoJSON y mapas de dispersión
geográfica por localidad con tiempos de traslado a centros de salud.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from health_data.processing.cartografia import poner_clave_cvegeo

# Paleta cromática institucional de Sonora y salud
COLOR_SONORA = "#C1440E"  # Terracota Unison
COLOR_NACIONAL = "#1F4E79"  # Azul institucional
COLOR_REFERENCIA = "#8C8C8C"  # Gris neutral
COLOR_ALERTA = "#B00020"  # Rojo crítico (> 120 min)
COLOR_PRECAUCION = "#EF6C00"  # Naranja intermedio (60 - 120 min)
COLOR_ADECUADO = "#2E7D32"  # Verde (< 60 min)

SECUENCIA_MAPA = "RdYlGn_r"  # Invertido: rojo = alto tiempo (peor), verde = bajo tiempo (mejor)
PLANTILLA = "plotly_white"

MENSAJE_SIN_DATOS = "No hay datos suficientes para mostrar esta visualización."


def _figura_vacia(mensaje: str = MENSAJE_SIN_DATOS) -> go.Figure:
    """Genera una figura vacía con un mensaje informativo centrado."""
    figura = go.Figure()
    figura.add_annotation(
        text=mensaje,
        showarrow=False,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        font=dict(size=14, color=COLOR_REFERENCIA),
    )
    figura.update_layout(
        template=PLANTILLA,
        height=350,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return figura


def mapa_municipios(
    datos: pd.DataFrame,
    geojson: dict | None,
    *,
    columna: str = "primary_time_min",
    columna_nombre: str = "municipality_name",
    titulo: str = "Tiempo promedio de traslado a salud por municipio",
    unidad: str = "minutos",
    minimo_localidades: int = 1,
) -> go.Figure:
    """Genera un mapa coroplético de los 72 municipios de Sonora.

    Empata los datos con el GeoJSON usando la clave INEGI `cvegeo` de 5 dígitos.
    """
    if datos is None or datos.empty or columna not in datos.columns:
        return _figura_vacia("Sin datos municipales para graficar.")

    if not geojson:
        return _figura_vacia(
            "Sin cartografía municipal en memoria. Ejecute la descarga de cartografía."
        )

    datos_mapa = poner_clave_cvegeo(datos)
    claves_geo = {
        str((f.get("properties", {}) or {}).get("cvegeo", "")).strip()
        for f in geojson.get("features", [])
    }
    empata = datos_mapa["clave_cvegeo"].isin(claves_geo)

    if not empata.any():
        return _figura_vacia("Las claves de municipio no empataron con el GeoJSON.")

    sub = datos_mapa[empata].copy()
    col_nombre_real = (
        columna_nombre if columna_nombre in sub.columns else "clave_cvegeo"
    )

    figura = go.Figure(
        go.Choropleth(
            geojson=geojson,
            locations=sub["clave_cvegeo"],
            featureidkey="properties.cvegeo",
            z=sub[columna],
            colorscale=SECUENCIA_MAPA,
            marker_line_color="white",
            marker_line_width=0.8,
            colorbar=dict(title=unidad),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                + f"{titulo}: "
                + "%{z:,.1f} "
                + unidad
                + "<extra></extra>"
            ),
            customdata=sub[[col_nombre_real]].to_numpy(),
        )
    )

    figura.update_geos(
        fitbounds="locations",
        visible=False,
        bgcolor="rgba(0,0,0,0)",
        showcountries=False,
    )
    figura.update_layout(
        template=PLANTILLA,
        title=titulo,
        height=580,
        margin=dict(t=60, b=10, l=10, r=10),
    )
    return figura


def mapa_localidades(
    localidades: pd.DataFrame,
    *,
    columna: str = "primary_time_min",
    columna_nombre: str = "locality_name",
    columna_municipio: str = "municipality_name",
    titulo: str = "Accesibilidad geográfica de las localidades de Sonora",
    unidad: str = "minutos",
    max_puntos: int = 5000,
    columna_metodo: str | None = None,
) -> go.Figure:
    """Mapa de puntos (Scattermapbox) para localidades individuales.

    Muestra cada localidad con color gradual según tiempo de traslado hacia la clínica más cercana.
    Con ``columna_metodo`` (``sakbe``/``estimado``) el tooltip indica si el tiempo fue medido o estimado.
    """
    if (
        localidades is None
        or localidades.empty
        or not {"latitude", "longitude"}.issubset(localidades.columns)
    ):
        return _figura_vacia(
            "Sin datos de coordenadas (latitude, longitude) para localidades."
        )

    datos = localidades.dropna(subset=["latitude", "longitude"]).copy()
    if columna in datos.columns:
        datos = datos[datos[columna].notna()].copy()

    if len(datos) > max_puntos:
        # Muestreo estratificado o recorte si excede el límite para rendimiento web
        datos = datos.sample(max_puntos, random_state=42)

    col_nom = (
        columna_nombre if columna_nombre in datos.columns else "locality_id"
    )
    col_mun = (
        columna_municipio
        if columna_municipio in datos.columns
        else "municipio"
    )
    poblacion = (
        datos["population"]
        if "population" in datos.columns
        else pd.Series(10, index=datos.index)
    )

    tamano_burbuja = np.clip(
        np.sqrt(pd.to_numeric(poblacion, errors="coerce").fillna(10)) / 4, 4, 15
    )

    columnas_hover = [col_nom, col_mun]
    plantilla_hover = "<b>%{customdata[0]}</b> (%{customdata[1]})"
    if columna in datos.columns:
        columnas_hover.append(columna)
        plantilla_hover += f"<br>{unidad}: %{{customdata[2]:,.1f}}"
        if columna_metodo and columna_metodo in datos.columns:
            datos["_origen"] = (
                datos[columna_metodo]
                .map({"sakbe": "medido con SAKBÉ", "estimado": "estimado"})
                .fillna("estimado")
            )
            columnas_hover.append("_origen")
            plantilla_hover += " (%{customdata[3]})"
    plantilla_hover += "<extra></extra>"

    figura = go.Figure(
        go.Scattermapbox(
            lat=datos["latitude"],
            lon=datos["longitude"],
            mode="markers",
            marker=dict(
                size=tamano_burbuja,
                color=datos[columna] if columna in datos.columns else COLOR_SONORA,
                colorscale=SECUENCIA_MAPA,
                showscale=bool(columna in datos.columns),
                colorbar=dict(title=unidad) if columna in datos.columns else None,
                opacity=0.8,
            ),
            customdata=datos[columnas_hover].to_numpy(),
            hovertemplate=plantilla_hover,
        )
    )

    # Centro geográfico aproximado de Sonora
    lat_centro = float(datos["latitude"].median())
    lon_centro = float(datos["longitude"].median())

    figura.update_layout(
        template=PLANTILLA,
        title=titulo,
        height=620,
        mapbox=dict(
            style="carto-positron",
            zoom=5.8,
            center=dict(lat=lat_centro, lon=lon_centro),
        ),
        margin=dict(t=60, b=10, l=10, r=10),
    )
    return figura


def histograma_tiempos(
    tabla: pd.DataFrame,
    *,
    columna: str = "primary_time_min",
    titulo: str = "Distribución del tiempo de traslado hacia centros de salud",
    unidad: str = "minutos",
    umbral_critico: float = 60.0,
) -> go.Figure:
    """Histograma de distribución con línea vertical de umbral crítico."""
    if tabla is None or tabla.empty or columna not in tabla.columns:
        return _figura_vacia()

    valores = pd.to_numeric(tabla[columna], errors="coerce").dropna()
    if valores.empty:
        return _figura_vacia()

    figura = go.Figure(
        go.Histogram(
            x=valores,
            nbinsx=40,
            marker_color=COLOR_NACIONAL,
            opacity=0.85,
            hovertemplate="Rango: %{x} "
            + unidad
            + "<br>Localidades: %{y}<extra></extra>",
        )
    )

    figura.add_vline(
        x=umbral_critico,
        line_dash="dash",
        line_color=COLOR_ALERTA,
        line_width=2,
        annotation_text=f"Umbral crítico ({umbral_critico:.0f} min)",
        annotation_position="top right",
    )

    mediana = float(valores.median())
    figura.add_vline(
        x=mediana,
        line_dash="dot",
        line_color=COLOR_SONORA,
        line_width=2,
        annotation_text=f"Mediana ({mediana:.1f} min)",
        annotation_position="top left",
    )

    figura.update_layout(
        template=PLANTILLA,
        title=titulo,
        xaxis_title=f"Tiempo de traslado ({unidad})",
        yaxis_title="Número de localidades",
        height=450,
        margin=dict(t=60, b=40, l=50, r=20),
    )
    return figura


def ranking_municipios(
    tabla: pd.DataFrame,
    *,
    columna: str = "primary_time_min",
    columna_nombre: str = "municipality_name",
    titulo: str = "Municipios con mayor tiempo promedio de traslado",
    unidad: str = "minutos",
    top_n: int = 15,
) -> go.Figure:
    """Gráfico de barras horizontales ordenado con los municipios más vulnerables."""
    if tabla is None or tabla.empty or columna not in tabla.columns:
        return _figura_vacia()

    datos = (
        tabla.groupby(columna_nombre)[columna]
        .mean()
        .reset_index()
        .sort_values(columna, ascending=True)
        .tail(top_n)
    )

    if datos.empty:
        return _figura_vacia()

    figura = go.Figure(
        go.Bar(
            x=datos[columna],
            y=datos[columna_nombre],
            orientation="h",
            marker_color=COLOR_SONORA,
            hovertemplate="%{y}: %{x:,.1f} " + unidad + "<extra></extra>",
        )
    )

    figura.update_layout(
        template=PLANTILLA,
        title=titulo,
        xaxis_title=f"Promedio ({unidad})",
        yaxis_title="",
        height=max(400, top_n * 28),
        margin=dict(t=60, b=40, l=120, r=20),
    )
    return figura


def barras_poblacion_por_rango(
    rangos: dict[str, pd.DataFrame],
    *,
    titulo: str = "Población por tiempo de traslado al establecimiento más cercano",
) -> go.Figure:
    """Barras agrupadas de población por rango de tiempo, una serie por nivel de atención.

    ``rangos`` mapea el nombre del nivel a la salida de ``analisis.poblacion_por_rango``.
    El eje vertical es logarítmico porque casi toda la población está en el primer rango.
    """
    if not rangos or all(r is None or r.empty for r in rangos.values()):
        return _figura_vacia()

    colores = [COLOR_NACIONAL, COLOR_SONORA, COLOR_REFERENCIA]
    figura = go.Figure()
    for (nombre, datos), color in zip(rangos.items(), colores):
        figura.add_bar(
            x=datos.index.astype(str),
            y=datos["poblacion"],
            name=nombre,
            marker_color=color,
            customdata=datos[["pct_poblacion", "localidades"]].to_numpy(),
            hovertemplate="%{x}<br>%{y:,} personas (%{customdata[0]:.1f} %)"
            "<br>%{customdata[1]:,} localidades<extra>" + nombre + "</extra>",
        )
    figura.update_layout(
        template=PLANTILLA,
        title=titulo,
        xaxis_title="Tiempo de traslado",
        yaxis_title="Personas (escala logarítmica)",
        yaxis_type="log",
        barmode="group",
        height=420,
        margin=dict(t=60, b=40, l=60, r=20),
    )
    return figura


def barras_municipios_comprometidos(
    resumen: pd.DataFrame,
    *,
    top_n: int = 15,
    titulo: str = "Municipios con más población con acceso comprometido",
) -> go.Figure:
    """Barras horizontales de población con acceso comprometido por municipio.

    Usa la salida de ``analisis.resumen_municipal``. El color indica qué porcentaje
    del municipio representa esa población.
    """
    if resumen is None or resumen.empty or "poblacion_comprometida" not in resumen.columns:
        return _figura_vacia()

    datos = resumen[resumen["poblacion_comprometida"] > 0].head(top_n).iloc[::-1]
    if datos.empty:
        return _figura_vacia("Ningún municipio supera los umbrales seleccionados.")

    figura = go.Figure(
        go.Bar(
            x=datos["poblacion_comprometida"],
            y=datos["municipio"],
            orientation="h",
            marker=dict(
                color=datos["pct_poblacion_comprometida"],
                colorscale="OrRd",
                colorbar=dict(title="% del<br>municipio"),
            ),
            customdata=datos[["pct_poblacion_comprometida", "tiempo_segundo_ponderado"]].to_numpy(),
            hovertemplate="<b>%{y}</b><br>%{x:,} personas (%{customdata[0]:.1f} % del municipio)"
            "<br>Tiempo promedio al 2do nivel: %{customdata[1]:.0f} min<extra></extra>",
        )
    )
    figura.update_layout(
        template=PLANTILLA,
        title=titulo,
        xaxis_title="Personas",
        yaxis_title="",
        height=max(400, len(datos) * 30 + 100),
        margin=dict(t=60, b=40, l=120, r=20),
    )
    return figura


def barras_grupos_vulnerables(
    grupos: pd.DataFrame,
    *,
    titulo: str = "Porcentaje de cada grupo que vive con acceso comprometido",
) -> go.Figure:
    """Barras del porcentaje de cada grupo con acceso comprometido.

    Usa la salida de ``analisis.grupos_vulnerables``; la primera fila (población
    total) se dibuja en gris como referencia.
    """
    if grupos is None or grupos.empty:
        return _figura_vacia()

    colores = [COLOR_REFERENCIA] + [COLOR_SONORA] * (len(grupos) - 1)
    figura = go.Figure(
        go.Bar(
            x=grupos["pct_comprometido"],
            y=grupos["grupo"],
            orientation="h",
            marker_color=colores,
            text=grupos["con_acceso_comprometido"].map("{:,} personas".format),
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:.2f} % del grupo<extra></extra>",
        )
    )
    figura.update_layout(
        template=PLANTILLA,
        title=titulo,
        xaxis_title="% del grupo en el estado",
        yaxis=dict(autorange="reversed"),
        height=400,
        margin=dict(t=60, b=40, l=260, r=120),
    )
    return figura
