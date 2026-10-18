"""Tablero principal de Data Health MCD Unison.

Accesibilidad geográfica a servicios de salud de primer y segundo nivel en Sonora.
Los indicadores se calculan con ``health_data.analisis``.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_RAIZ = Path(__file__).resolve().parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from health_data import analisis, config  # noqa: E402
from health_data.processing import cartografia  # noqa: E402
from health_data.visualization import mapas  # noqa: E402

log = logging.getLogger("health_data.tablero")

NOMBRE_PROYECTO = "Accesibilidad a Servicios de Salud en Sonora"
PROGRAMA_MCD = "Maestría en Ciencia de Datos"
SITIO_MCD = "https://mcd.unison.mx/"
RUTA_LOGO_MCD = _RAIZ / "assets" / "logo_mcd.png"

PAGINAS = [
    "🗺️ Panorama",
    "📊 Municipios",
    "📍 Localidades prioritarias",
    "👥 Grupos vulnerables",
    "📋 Tabla de localidades",
    "🔍 Metodología y fuentes",
]
NIVELES = {
    "Primer nivel (centros de salud)": ("primer", "primary_time_min", "primary_method", "nearest_primary_clues"),
    "Segundo nivel (hospitales)": ("segundo", "secondary_time_min", "secondary_method", "nearest_secondary_clues"),
}

# Nombres para mostrar en las tablas
ETIQUETAS = {
    "municipio": "Municipio",
    "municipality_name": "Municipio",
    "locality_name": "Localidad",
    "locality_id": "Clave",
    "population": "Población",
    "poblacion": "Población",
    "localidades": "Localidades",
    "primary_time_min": "Min. a 1er nivel",
    "primary_method": "Origen 1er nivel",
    "secondary_time_min": "Min. a 2do nivel",
    "secondary_method": "Origen 2do nivel",
    "routing_status": "Estado de ruta",
    "pct_60_y_mas": "% 60 y más",
    "pct_con_discapacidad": "% con discapacidad",
    "pct_sin_afiliacion": "% sin afiliación",
    "pct_lengua_indigena": "% lengua indígena",
    "pct_viviendas_sin_auto_ni_moto": "% viviendas sin vehículo",
    "poblacion_comprometida": "Población con acceso comprometido",
    "pct_poblacion_comprometida": "% del municipio",
    "localidades_comprometidas": "Localidades comprometidas",
    "poblacion_primer_critico": "Población > umbral 1er nivel",
    "poblacion_segundo_critico": "Población > umbral 2do nivel",
    "tiempo_primer_ponderado": "Min. promedio a 1er nivel",
    "tiempo_segundo_ponderado": "Min. promedio a 2do nivel",
    "pct_localidades_sakbe": "% localidades medidas",
    "grupo": "Grupo",
    "total_estado": "Total en el estado",
    "con_acceso_comprometido": "Con acceso comprometido",
    "pct_comprometido": "% del grupo",
}

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

        pagina = st.radio("Vista", PAGINAS, index=0)

        st.divider()
        nivel = st.radio(
            "Nivel de atención (mapas y tiempos)",
            list(NIVELES),
            index=0,
            help="El primer nivel atiende medicina preventiva y consulta ambulatoria. El segundo nivel brinda hospitalización y especialidades básicas.",
        )

        st.markdown("**Umbrales de acceso comprometido**")
        umbral_primer = st.slider(
            "1er nivel (minutos)",
            min_value=15,
            max_value=120,
            value=int(cfg.umbrales.tiempo_critico_min),
            step=15,
            help="Tiempo de traslado a partir del cual el acceso a un centro de salud se considera comprometido.",
        )
        umbral_segundo = st.slider(
            "2do nivel (minutos)",
            min_value=30,
            max_value=240,
            value=int(cfg.umbrales.tiempo_critico_segundo_nivel_min),
            step=15,
            help="Tiempo de traslado a partir del cual el acceso a un hospital se considera comprometido. "
            "El proyecto usa 120 min: quien necesita un hospital suele llegar en una condición en la que cada minuto cuenta.",
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
        "umbral_primer": float(umbral_primer),
        "umbral_segundo": float(umbral_segundo),
        "municipio": municipio_filtro,
    }


# --------------------------------------------------------------------------
# Componentes
# --------------------------------------------------------------------------


def tabla_legible(datos: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    """Selecciona columnas existentes y las renombra para mostrarlas."""
    presentes = [c for c in columnas if c in datos.columns]
    salida = datos[presentes].rename(columns=ETIQUETAS)
    for col in salida.columns:
        if col.startswith("Origen"):
            salida[col] = salida[col].map({"sakbe": "SAKBÉ", "coneval": "CONEVAL", "estimado": "Estimado"}).fillna(salida[col])
    return salida


def aviso_cobertura(resumen: dict[str, float]) -> None:
    """Explica qué parte de los tiempos se midió con SAKBÉ."""
    if resumen["pct_localidades_sakbe"] >= 99.9:
        return
    st.info(
        f"Tiempos medidos con SAKBÉ en **{resumen['pct_localidades_sakbe']:.1f} %** de las localidades, "
        f"donde vive el **{resumen['pct_poblacion_sakbe']:.1f} %** de la población. "
        "El resto usa una estimación por línea recta que, en zonas alejadas, ha resultado menor "
        "que el tiempo real; las cifras de esas localidades pueden aumentar al completar las rutas."
    )


def pie_de_fuentes(tabla: pd.DataFrame) -> None:
    """Cita de fuentes exigida por las condiciones de uso de la API de Ruteo de INEGI."""
    periodo = ""
    if "routing_consulted_at" in tabla.columns:
        fechas = pd.to_datetime(tabla["routing_consulted_at"], errors="coerce").dropna()
        if not fechas.empty:
            inicio, fin = fechas.min().date(), fechas.max().date()
            periodo = f" (consultas del {inicio} al {fin})" if inicio != fin else f" (consulta del {inicio})"
    st.divider()
    st.caption(
        f"Fuentes: INEGI, API de Ruteo SAKBÉ v3.1{periodo}; INEGI, Censo de Población y Vivienda 2020 (ITER) "
        "y Marco Geoestadístico; Secretaría de Salud, CLUES; CONEVAL, Grado de accesibilidad a carretera "
        "pavimentada 2020. Elaboración propia. Tiempos para automóvil en condiciones óptimas."
    )


# --------------------------------------------------------------------------
# Vistas
# --------------------------------------------------------------------------


def vista_panorama(tabla: pd.DataFrame, c: dict, umbrales: dict, nivel: tuple) -> None:
    clave_nivel, col_tiempo, col_metodo, _ = nivel
    resumen = analisis.resumen_estatal(tabla, **umbrales)

    st.title(NOMBRE_PROYECTO)
    st.markdown(
        "¿Dónde se concentran las poblaciones de Sonora con menor accesibilidad geográfica a servicios de salud? "
        f"Una localidad tiene **acceso comprometido** si está a más de **{c['umbral_primer']:.0f} min** "
        f"de un centro de salud o a más de **{c['umbral_segundo']:.0f} min** de un hospital."
    )
    if c["municipio"] != "Todos":
        st.caption(f"Municipio: **{c['municipio']}**")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Población con acceso comprometido", f"{resumen['poblacion_comprometida']:,}")
    k2.metric("% de la población", f"{resumen['pct_poblacion_comprometida']:.2f} %")
    k3.metric("Localidades con acceso comprometido", f"{resumen['localidades_comprometidas']:,} de {resumen['localidades']:,}")
    tiempo = resumen["tiempo_primer_ponderado" if clave_nivel == "primer" else "tiempo_segundo_ponderado"]
    k4.metric(
        f"Tiempo promedio al {clave_nivel} nivel",
        f"{tiempo:.0f} min",
        help="Promedio ponderado por población: el tiempo que enfrenta una persona típica, no una localidad típica.",
    )
    aviso_cobertura(resumen)

    solo_comprometidas = st.toggle("Mostrar solo localidades con acceso comprometido", value=False)
    datos_mapa = tabla[analisis.acceso_comprometido(tabla, **umbrales)] if solo_comprometidas else tabla
    st.plotly_chart(
        mapas.mapa_localidades(
            datos_mapa,
            columna=col_tiempo,
            columna_metodo=col_metodo,
            max_puntos=max(len(datos_mapa), 1),
            titulo=f"Tiempo de traslado al establecimiento de {clave_nivel} nivel más cercano",
        ),
        use_container_width=True,
    )

    st.plotly_chart(
        mapas.barras_poblacion_por_rango(
            {
                "1er nivel": analisis.poblacion_por_rango(tabla, "primer", umbrales["umbrales"]),
                "2do nivel": analisis.poblacion_por_rango(tabla, "segundo", umbrales["umbrales"]),
            }
        ),
        use_container_width=True,
    )
    st.caption(
        "Escala logarítmica: casi toda la población vive cerca de un establecimiento, "
        "y los rangos altos tienen pocas personas."
    )


def vista_municipios(tabla: pd.DataFrame, c: dict, umbrales: dict, nivel: tuple, geojson: dict | None) -> None:
    clave_nivel = nivel[0]
    st.title("Accesibilidad por municipio")
    st.markdown(
        "Los tiempos promedio se **ponderan por población**. La mayoría de las localidades tiene menos de "
        "10 habitantes, así que un promedio simple por localidad exageraría el peso de las más pequeñas."
    )
    resumen = analisis.resumen_municipal(tabla, **umbrales)
    if resumen.empty:
        st.info("Sin datos para los filtros seleccionados.")
        return

    indicador = st.radio(
        "Indicador del mapa",
        ["% de la población con acceso comprometido", f"Tiempo promedio al {clave_nivel} nivel"],
        horizontal=True,
    )
    columna = (
        "pct_poblacion_comprometida"
        if indicador.startswith("%")
        else ("tiempo_primer_ponderado" if clave_nivel == "primer" else "tiempo_segundo_ponderado")
    )
    col_izq, col_der = st.columns([1.2, 1])
    with col_izq:
        st.plotly_chart(
            mapas.mapa_municipios(
                resumen,
                geojson,
                columna=columna,
                columna_nombre="municipio",
                titulo=indicador,
                unidad="%" if columna.startswith("pct") else "minutos",
            ),
            use_container_width=True,
        )
    with col_der:
        st.plotly_chart(mapas.barras_municipios_comprometidos(resumen), use_container_width=True)

    st.subheader("Indicadores por municipio")
    st.dataframe(
        tabla_legible(
            resumen,
            [
                "municipio",
                "poblacion",
                "poblacion_comprometida",
                "pct_poblacion_comprometida",
                "localidades_comprometidas",
                "poblacion_primer_critico",
                "poblacion_segundo_critico",
                "tiempo_primer_ponderado",
                "tiempo_segundo_ponderado",
                "pct_localidades_sakbe",
            ],
        ).round(1),
        use_container_width=True,
        hide_index=True,
    )


def vista_prioritarias(tabla: pd.DataFrame, umbrales: dict) -> None:
    st.title("Localidades prioritarias")
    prioritarias = analisis.localidades_prioritarias(tabla, n=None, **umbrales)
    st.markdown(
        f"**{len(prioritarias):,} localidades** con acceso comprometido, donde viven "
        f"**{int(prioritarias['population'].sum()):,} personas**, ordenadas de mayor a menor población. "
        "La columna *Origen* indica si el tiempo se midió con SAKBÉ o se estimó."
    )
    if prioritarias.empty:
        st.success("Ninguna localidad supera los umbrales seleccionados.")
        return
    columnas = [
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
    ]
    st.dataframe(tabla_legible(prioritarias, columnas).round(1), use_container_width=True, hide_index=True)
    st.caption("Los porcentajes de vulnerabilidad vienen vacíos en las localidades que ITER publica como confidenciales.")
    st.download_button(
        "Descargar localidades prioritarias en CSV",
        data=prioritarias.to_csv(index=False).encode("utf-8-sig"),
        file_name="localidades_prioritarias_salud_sonora.csv",
        mime="text/csv",
    )


def vista_grupos(tabla: pd.DataFrame, umbrales: dict) -> None:
    st.title("Grupos vulnerables con acceso comprometido")
    grupos = analisis.grupos_vulnerables(tabla, **umbrales)
    resumen = analisis.resumen_estatal(tabla, **umbrales)
    st.markdown(
        "Personas de cada grupo que viven en localidades con acceso comprometido. "
        "Si la barra de un grupo es más larga que la de la **población total**, ese grupo está "
        "sobrerrepresentado entre quienes tienen acceso comprometido."
    )
    st.plotly_chart(mapas.barras_grupos_vulnerables(grupos), use_container_width=True)
    st.dataframe(tabla_legible(grupos, list(grupos.columns)).round(2), use_container_width=True, hide_index=True)
    st.caption(
        f"ITER no publica estas variables en localidades confidenciales; los grupos cubren al "
        f"{resumen['pct_poblacion_con_datos_vulnerabilidad']:.1f} % de la población. La población sin automóvil "
        "ni motocicleta se estima como población × porcentaje de viviendas sin vehículo."
    )


def vista_tabla(tabla: pd.DataFrame) -> None:
    st.title("Catálogo de localidades y accesibilidad")
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.download_button(
        "Descargar datos en CSV",
        data=tabla.to_csv(index=False).encode("utf-8-sig"),
        file_name="accesibilidad_salud_sonora.csv",
        mime="text/csv",
    )


def vista_metodologia(tabla: pd.DataFrame, cfg: config.Configuracion, manifiesto: dict) -> None:
    st.title("Metodología, fuentes y calidad")
    u = cfg.umbrales
    st.markdown(
        f"""
    ### Cómo se calcula el tiempo de traslado
    1. Para cada localidad se eligen los **2 establecimientos operativos más cercanos en línea recta** por nivel de atención.
    2. Con la **API de Ruteo SAKBÉ de INEGI** se mide la ruta por carretera hacia cada uno y se conserva la de menor tiempo.
    3. Si la clínica queda sobre el mismo tramo carretero que la localidad, el traslado se considera local (mínimo 3 min).
    4. **Sin carretera cercana** (SAKBÉ no encuentra ruta): se asigna el tiempo típico medido con SAKBÉ en las localidades del **mismo municipio y con el mismo grado de aislamiento de CONEVAL** (tiempo al centro de servicios). Si hay menos de 5 localidades así en el municipio, se usa la de todo el estado. Comparado con las rutas reales, acierta si la localidad supera el umbral en ~91 % (hospital) y ~84 % (centro de salud) de los casos en zonas alejadas.
    5. Las localidades aún no consultadas usan una **estimación**: distancia en línea recta × 1.28 de sinuosidad y velocidades promedio. En zonas alejadas subestima el tiempo real, por lo que solo es provisional.

    Las rutas se consultan de la localidad más poblada a la menos poblada, por lo que la población cubierta avanza más rápido que el número de localidades.

    | Estado de ruta | Significado |
    |---|---|
    | `ok` | Ambos niveles medidos con SAKBÉ |
    | `parcial` | Solo un nivel medido con SAKBÉ |
    | `sin_ruta` | SAKBÉ no encontró carretera cercana; tiempo asignado con CONEVAL (paso 4) |
    | `estimado` | Aún no consultada; se usa la estimación |

    La columna *Origen* de las tablas indica, por nivel, si el tiempo viene de **SAKBÉ**, de **CONEVAL** o de la **estimación**.

    ### Umbrales del proyecto
    - **1er nivel:** más de {u.tiempo_critico_min} min a un centro de salud.
    - **2do nivel:** más de {u.tiempo_critico_segundo_nivel_min} min a un hospital. Se eligió un umbral estricto porque quien necesita un hospital suele llegar en una condición en la que cada minuto cuenta.

    ### Fuentes de información
    - **ITER 2020 (INEGI):** población y características de las localidades (edad, discapacidad, afiliación, lengua indígena, viviendas sin vehículo).
    - **Directorio de Establecimientos de Salud (CLUES, Secretaría de Salud):** establecimientos operativos y fijos de 1er y 2do nivel.
    - **Marco Geoestadístico (INEGI):** límites municipales de Sonora y validación de coordenadas.
    - **API de Ruteo SAKBÉ v3.1 (INEGI):** tiempos y distancias por la red carretera para automóvil en condiciones óptimas.
    - **Grado de Accesibilidad a Carretera Pavimentada 2020 (CONEVAL):** movilidad y aislamiento de las localidades.

    ### Alcance y limitaciones
    Este proyecto mide **accesibilidad geográfica potencial en automóvil**. No evalúa:
    - El tiempo dentro del establecimiento (espera y atención), que se analizará en una etapa posterior.
    - Capacidad o saturación de camas hospitalarias, ni disponibilidad de medicamentos o insumos.
    - Horarios ni frecuencias del transporte público; para quien no tiene vehículo el tiempo real es mayor.
    - Las variables de vulnerabilidad de las localidades confidenciales de ITER.
    """
    )

    if manifiesto:
        validacion = manifiesto.get("validacion")
        if validacion:
            st.subheader("Validación de calidad")
            if validacion.get("paso"):
                st.success(f"{validacion.get('comprobaciones', 0)} comprobaciones superadas.")
            else:
                for falla in validacion.get("fallidas", []):
                    st.warning(f"**{falla['nombre']}:** {falla['detalle']}")
        st.subheader("Manifiesto de ejecución")
        st.json(manifiesto, expanded=False)


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
        col4.metric("SAKBÉ (Ruteo)", "Integrada")

        st.markdown(
            """
        ### Objetivo del proyecto
        Para cada localidad de Sonora se identificará:
        - Establecimiento operativo de **primer nivel** más cercano y tiempo de traslado.
        - Establecimiento operativo de **segundo nivel** más cercano y tiempo de traslado.
        - Relación con factores sociodemográficos (edad, discapacidad, disponibilidad de vehículo privado).
        """
        )
        return

    # Si hay filtro de municipio aplicado
    if controles["municipio"] != "Todos":
        tabla = tabla[tabla["municipality_name"] == controles["municipio"]].copy()

    nivel = NIVELES[str(controles["nivel"])]
    umbrales = {
        "umbral_primer": controles["umbral_primer"],
        "umbral_segundo": controles["umbral_segundo"],
        "umbrales": cfg.umbrales,
    }
    pagina = controles["pagina"]

    # Si la tabla actual es solo el intermedio de CONEVAL (sin ruteo aún)
    tiene_ruteo = {"primary_time_min", "secondary_time_min"}.issubset(tabla.columns)
    if not tiene_ruteo and pagina not in ("📋 Tabla de localidades", "🔍 Metodología y fuentes"):
        st.title(NOMBRE_PROYECTO)
        st.warning(
            "Mostrando datos intermedios de CONEVAL-ACC-001. Los indicadores de accesibilidad "
            "se habilitarán al ejecutar el pipeline (`make data`)."
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
        return

    if pagina == "🗺️ Panorama":
        vista_panorama(tabla, controles, umbrales, nivel)
    elif pagina == "📊 Municipios":
        vista_municipios(tabla, controles, umbrales, nivel, geojson)
    elif pagina == "📍 Localidades prioritarias":
        vista_prioritarias(tabla, umbrales)
    elif pagina == "👥 Grupos vulnerables":
        vista_grupos(tabla, umbrales)
    elif pagina == "📋 Tabla de localidades":
        vista_tabla(tabla)
    elif pagina == "🔍 Metodología y fuentes":
        vista_metodologia(tabla, cfg, manifiesto)

    pie_de_fuentes(tabla)


if __name__ == "__main__":
    main()
