"""Tablero principal de Data Health MCD Unison."""

import streamlit as st


st.set_page_config(
    page_title="Data Health MCD Unison",
    page_icon="📊",
    layout="wide",
)

st.title("Data Health MCD Unison")

st.info(
    "El entorno del proyecto está configurado correctamente. "
    "El siguiente paso es incorporar las fuentes de datos y "
    "desarrollar el pipeline."
)

st.subheader("Estado del proyecto")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Fuentes cargadas", 0)

with col2:
    st.metric("Registros procesados", 0)

with col3:
    st.metric("Indicadores generados", 0)