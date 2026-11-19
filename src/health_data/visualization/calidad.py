"""Vista de procedencia de los tiempos de acceso."""

import pandas as pd
import streamlit as st

from health_data.calidad_ruteo import padron_provisional, tiempos_por_nivel

PAGINA = "Calidad de datos"
ETIQUETAS = {"sakbe": "SAKBÉ", "coneval": "Respaldo CONEVAL",
             "estimado": "Estimado", "sin_dato": "Método sin dato"}


def vista(tabla: pd.DataFrame) -> None:
    st.title(PAGINA)
    if tabla.empty:
        st.info("Genere la tabla de accesibilidad para consultar la procedencia de los tiempos.")
        return

    municipios = sorted(tabla["municipality_name"].dropna().unique())
    elegir = st.selectbox("Municipio", ["Todos", *municipios], key="calidad_municipio")
    if elegir != "Todos":
        tabla = tabla.loc[tabla["municipality_name"].eq(elegir)]
    datos = tiempos_por_nivel(tabla)
    fechas = pd.to_datetime(datos["routing_consulted_at"], errors="coerce", utc=True)
    corte = fechas.max()
    texto_corte = corte.strftime("%Y-%m-%d (UTC)") if pd.notna(corte) else "sin fecha registrada"
    st.caption(f"Última consulta SAKBÉ registrada para esta selección · {texto_corte}. "
               "Los respaldos CONEVAL y las estimaciones se interpretan como aproximaciones.")
    for nivel, grupo in datos.groupby("nivel", sort=False):
        st.subheader(nivel)
        columnas = st.columns(len(ETIQUETAS))
        for columna, (metodo, etiqueta) in zip(columnas, ETIQUETAS.items()):
            columna.metric(etiqueta, int(grupo["metodo"].eq(metodo).sum()))

    metodo = st.selectbox("Método del tiempo", ["Todos", *ETIQUETAS],
                          format_func=lambda valor: ETIQUETAS.get(valor, valor))
    if metodo != "Todos":
        datos = datos.loc[datos["metodo"].eq(metodo)]
    st.subheader("Padrón provisional de revisión")
    st.caption("Se construye a partir de la tabla actual. Los 58 casos históricos requieren su propia evidencia.")
    padron = padron_provisional(datos)
    st.dataframe(padron, hide_index=True)
    if not padron.empty:
        st.download_button("Descargar padrón CSV", padron.to_csv(index=False).encode("utf-8-sig"),
                           file_name="padron_provisional_ruteo.csv", mime="text/csv")
