import plotly.express as px
import streamlit as st

def mostrar_grafico_basa(df):
    """
    Genera y muestra el gráfico de barras para BASA.
    """
    fig = px.bar(
        df, 
        x="Titulo", 
        y="Reproducciones", 
        color="Tipo", 
        title="Quién se está pegando en BASA"
    )
    return st.plotly_chart(fig, use_container_width=True)
