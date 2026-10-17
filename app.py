"""Tablero principal de Data Health MCD Unison.

Accesibilidad geográfica a servicios de salud de primer y segundo nivel en Sonora.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

_RAIZ = Path(__file__).resolve().parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from health_data import config
from health_data.processing import cartografia
from health_data.visualization import mapas

log = logging.getLogger("health_data.tablero")

NOMBRE_PROYECTO = "Accesibilidad a Servicios de Salud en Sonora"
PROGRAMA_MCD = "Maestría en Ciencia de Datos"
SITIO_MCD = "https://mcd.unison.mx/"
RUTA_LOGO_MCD = _RAIZ / "assets" / "logo_mcd.png"

st.set_page_config(
    page_title=NOMBRE_PROYECTO,
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------
# Carga de datos en caché
# --------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def cargar_datos_procesados() -> pd.DataFrame:
    """Carga la tabla final consolidada si existe, o el intermedio disponible."""
    # 1. Tabla final completa de ruteo
    if config.ARCHIVO_TABLA_FINAL.exists():
        return pd.read_parquet(config.ARCHIVO_TABLA_FINAL)

    # 2. Respaldo intermedio CONEVAL-ACC-001 si ya fue generado
    archivo_coneval = (
        config.PROCESSED_DATA_DIR / "coneval-acc-001_localidades.parquet"
    )
    if archivo_coneval.exists():
        df = pd.read_parquet(archivo_coneval)
        # Asegurar columnas mínimas para demostración si aún no hay ruteo
        if "municipality_name" not in df.columns and "municipio" in df.columns:
            df["municipality_name"] = df["municipio"]
        if "locality_name" not in df.columns and "localidad" in df.columns:
            df["locality_name"] = df["localidad"]
        return df

    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def cargar_geojson_sonora() -> dict | None:
    """Carga la cartografía vectorial de los 72 municipios de Sonora."""
    cartografia.asegurar_cartografia()
    return cartografia.cargar_geojson(cartografia.NOMBRE_MUNICIPIOS_SONORA)


@st.cache_data(show_spinner=False)
def cargar_manifiesto() -> dict:
    """Lee el manifiesto de ejecución y trazabilidad si existe."""
    if not config.ARCHIVO_MANIFIESTO.exists():
        return {}
    try:
        with config.ARCHIVO_MANIFIESTO.open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


# --------------------------------------------------------------------------
# Barra lateral
# --------------------------------------------------------------------------


def barra_lateral(
    tabla: pd.DataFrame, cfg: config.Configuracion
) -> dict[str, object]:
    """Renderiza controles y filtros globales en la barra lateral."""
    with st.sidebar:
        if RUTA_LOGO_MCD.is_file():
            try:
                st.image(str(RUTA_LOGO_MCD), width=120)
            except Exception:
                pass
        st.caption(f"**{PROGRAMA_MCD}** · [UNISON]({SITIO_MCD})")
        st.divider()

        st.title("Salud Sonora")
        st.caption(
            "Identificación de poblaciones con menor accesibilidad a salud."
        )

        pagina = st.radio(
            "Vista",
            [
                "🗺️ Mapa general",
                "📊 Análisis municipal",
                "📋 Tabla de localidades",
                "🔍 Metodología y fuentes",
            ],
            index=0,
        )

        st.divider()
        nivel = st.radio(
            "Nivel de atención",
            [
                "Primer nivel (Centros de Salud)",
                "Segundo nivel (Hospitales Generales)",
            ],
            index=0,
            help="El primer nivel atiende medicina preventiva y consulta ambulatoria. El segundo nivel brinda hospitalización y especialidades básicas.",
        )

        umbral_critico = st.slider(
            "Umbral crítico de traslado (minutos)",
            min_value=30,
            max_value=180,
            value=60,
            step=15,
            help="Tiempo estimado a partir del cual el traslado en vehículo se considera de muy baja accesibilidad.",
        )

        municipio_filtro = "Todos"
        if not tabla.empty and "municipality_name" in tabla.columns:
            municipios = ["Todos"] + sorted(
                tabla["municipality_name"].dropna().unique().tolist()
            )
            municipio_filtro = st.selectbox("Filtrar por municipio", municipios)

        st.divider()
        st.caption(
            "Proyecto académico de la Maestría en Ciencia de Datos, Universidad de Sonora."
        )

    return {
        "pagina": pagina,
        "nivel": nivel,
        "umbral_critico": umbral_critico,
        "municipio": municipio_filtro,
    }


# --------------------------------------------------------------------------
# Flujo Principal
# --------------------------------------------------------------------------


def main() -> None:
    cfg = config.cargar_configuracion()
    tabla = cargar_datos_procesados()
    geojson = cargar_geojson_sonora()
    manifiesto = cargar_manifiesto()

    controles = barra_lateral(tabla, cfg)

    # Si aún no hay datos generados en data/processed, mostrar pantalla de bienvenida defensiva
    if tabla.empty:
        st.title(NOMBRE_PROYECTO)
        st.info(
            "💡 **Entorno configurado correctamente.** "
            "Para generar el dataset final y habilitar los mapas interactivos, "
            "ejecute el pipeline de datos:"
        )
        st.code(
            "docker compose run --rm app python -m health_data.pipeline",
            language="powershell",
        )

        st.subheader("Estado de las fuentes de datos")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ITER 2020 (Población)", "Aprobada")
        col2.metric("CLUES (Establecimientos)", "Aprobada")
        col3.metric("Marco Geoestadístico", "Integrado")
        col4.metric("SAKBÉ (Ruteo)", "Pendiente")

        st.markdown(
            """
        ### Objetivo del proyecto
        Para cada localidad de Sonora se identificará:
        - Establecimiento operativo de **primer nivel** más cercano y tiempo de traslado.
        - Establecimiento operativo de **segundo nivel** más cercano y tiempo de traslado.
        - Correlación con factores sociodemográficos (edad, discapacidad, disponibilidad de vehículo privado).
        """
        )
        return

    # Si hay filtro de municipio aplicado
    if controles["municipio"] != "Todos":
        tabla = tabla[tabla["municipality_name"] == controles["municipio"]].copy()

    # Selección de columnas según nivel
    es_primer_nivel = "Primer nivel" in str(controles["nivel"])
    col_tiempo = (
        "primary_time_min" if es_primer_nivel else "secondary_time_min"
    )
    col_clues = (
        "nearest_primary_clues"
        if es_primer_nivel
        else "nearest_secondary_clues"
    )

    # Si la tabla actual es solo el intermedio de CONEVAL (sin ruteo aún)
    tiene_ruteo = col_tiempo in tabla.columns

    # ----------------------------------------------------------------------
    # Vistas
    # ----------------------------------------------------------------------

    pagina = controles["pagina"]

    if pagina == "🗺️ Mapa general":
        st.title(NOMBRE_PROYECTO)
        st.markdown(
            f"**Vista:** {controles['nivel']} · **Umbral crítico:** > {controles['umbral_critico']} min · **Municipio:** {controles['municipio']}"
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Localidades analizadas", f"{len(tabla):,}")

        if tiene_ruteo:
            rutas_ok = int(tabla["routing_status"].eq("ok").sum()) if "routing_status" in tabla.columns else len(tabla)
            c2.metric("Con ruta en red carretera", f"{rutas_ok:,}")
            mediana_tiempo = float(tabla[col_tiempo].median()) if col_tiempo in tabla.columns else 0.0
            c3.metric("Tiempo mediano", f"{mediana_tiempo:.1f} min")
            criticas = int((tabla[col_tiempo] > controles["umbral_critico"]).sum()) if col_tiempo in tabla.columns else 0
            c4.metric(f"> {controles['umbral_critico']} min", f"{criticas:,}")

            st.plotly_chart(
                mapas.mapa_localidades(
                    tabla,
                    columna=col_tiempo,
                    titulo=f"Tiempo de traslado al {controles['nivel']} más cercano",
                ),
                use_container_width=True,
            )
        else:
            c2.metric("Grado de accesibilidad (GACP)", "Disponible")
            c3.metric("Ruteo SAKBÉ", "En proceso")
            c4.metric("Municipios cubiertos", "72 de 72")

            st.warning(
                "Mostrando datos intermedios de CONEVAL-ACC-001. "
                "Las columnas de tiempo de traslado en minutos se habilitarán al ejecutar el ruteo de SAKBÉ."
            )
            if {"latitude", "longitude"}.issubset(tabla.columns):
                st.plotly_chart(
                    mapas.mapa_localidades(
                        tabla,
                        columna="grado_accesibilidad" if "grado_accesibilidad" in tabla.columns else "latitude",
                        titulo="Localidades de Sonora y grado de accesibilidad",
                    ),
                    use_container_width=True,
                )

    elif pagina == "📊 Análisis municipal":
        st.title("Análisis de accesibilidad por municipio")

        if tiene_ruteo:
            por_mun = (
                tabla.groupby("municipality_name")
                .agg(
                    tiempo_promedio=(col_tiempo, "mean"),
                    tiempo_mediano=(col_tiempo, "median"),
                    localidades=(col_tiempo, "count"),
                )
                .reset_index()
            )

            col_izq, col_der = st.columns([1.2, 1])
            with col_izq:
                st.plotly_chart(
                    mapas.mapa_municipios(
                        por_mun,
                        geojson,
                        columna="tiempo_promedio",
                        columna_nombre="municipality_name",
                        titulo=f"Tiempo promedio al {controles['nivel']} por municipio",
                    ),
                    use_container_width=True,
                )
            with col_der:
                st.plotly_chart(
                    mapas.ranking_municipios(
                        tabla,
                        columna=col_tiempo,
                        columna_nombre="municipality_name",
                        titulo="Top 15 municipios con mayores tiempos de traslado",
                    ),
                    use_container_width=True,
                )
                st.plotly_chart(
                    mapas.histograma_tiempos(
                        tabla,
                        columna=col_tiempo,
                        umbral_critico=float(controles["umbral_critico"]),
                    ),
                    use_container_width=True,
                )
        else:
            st.info(
                "El análisis municipal agregado requiere el cálculo de tiempos de SAKBÉ."
            )
            if "municipio" in tabla.columns and "grado_accesibilidad" in tabla.columns:
                resumen_gacp = (
                    tabla.groupby(["municipio", "grado_accesibilidad"], observed=True)
                    .size()
                    .unstack(fill_value=0)
                )
                st.dataframe(resumen_gacp, use_container_width=True)

    elif pagina == "📋 Tabla de localidades":
        st.title("Catálogo de localidades y accesibilidad")
        st.dataframe(tabla, use_container_width=True, hide_index=True)

        st.download_button(
            "Descargar datos en CSV",
            data=tabla.to_csv(index=False).encode("utf-8-sig"),
            file_name="accesibilidad_salud_sonora.csv",
            mime="text/csv",
        )

    elif pagina == "🔍 Metodología y fuentes":
        st.title("Metodología, Fuentes y Calidad")

        st.markdown(
            """
        ### Fuentes de información
        - **ITER 2020 (INEGI):** Características sociodemográficas de las localidades (población, edad, discapacidad, disponibilidad de automóvil).
        - **Directorio de Establecimientos de Salud (CLUES, Secretaría de Salud):** Identificación de oferta hospitalaria activa, filtrando unidades operativas y fijas de 1er y 2do nivel.
        - **Marco Geoestadístico (INEGI):** Geometrías oficiales de límites municipales de Sonora (`cvegeo`) y validación de coordenadas.
        - **API de Ruteo SAKBÉ (INEGI):** Tiempos y distancias óptimas de viaje por la red carretera nacional.
        - **Grado de Accesibilidad a Carretera Pavimentada (CONEVAL):** Movilidad sin automóvil y respaldo para localidades aisladas.

        ### Alcance y limitaciones
        Este proyecto mide **accesibilidad geográfica potencial**. No evalúa:
        - Tiempos de espera en consulta o urgencias.
        - Capacidad o saturación de camas hospitalarias.
        - Disponibilidad de medicamentos o insumos.
        - Horarios ni frecuencias del transporte público colectivo.
        """
        )

        if manifiesto:
            st.subheader("Manifiesto de ejecución")
            st.json(manifiesto)


if __name__ == "__main__":
    main()