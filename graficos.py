import plotly.express as px
import streamlit as st

def dibujar_grafico_basa(df):
    fig = px.bar(
        df, 
        x="Titulo", 
        y="Reproducciones", 
        color="Tipo", 
        title="Quién se está pegando en BASA"
    )
    st.plotly_chart(fig, use_container_width=True)
