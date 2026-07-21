"""
Módulo de Gráficos y Visualización de Plotly.

Este módulo encapsula la creación de figuras interactivas mediante Plotly Express,
aplicando una paleta de colores moderna y limpia de acuerdo con las directrices
de diseño del proyecto.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Paleta de colores armonizada para el dashboard (Neon Dark Mode)
PALETA_COLORES = ["#00D2FF", "#3A86FF", "#8338EC", "#FF006E", "#38B000"]
COLOR_SIMULADO = "#FF0000"  # Color especial si queremos destacar la simulación


def crear_grafico_barras_actividad(df: pd.DataFrame) -> go.Figure:
    """
    Genera un gráfico de barras horizontales mostrando el volumen presupuestario
    total acumulado por tipo de Actividad_Relacionada.
    """
    if df.empty:
        # Retorna una figura vacía con texto indicativo si no hay datos
        fig = go.Figure()
        fig.update_layout(
            title="Sin datos para mostrar",
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return fig

    # Agrupar datos por actividad y calcular la suma del presupuesto
    df_agrupado = (
        df.groupby("Actividad_Relacionada", as_index=False)["Cuantia"]
        .sum()
        .sort_values(by="Cuantia", ascending=True)
    )

    # Crear gráfico con Plotly Express
    fig = px.bar(
        df_agrupado,
        x="Cuantia",
        y="Actividad_Relacionada",
        orientation="h",
        labels={
            "Cuantia": "Presupuesto Total (€)",
            "Actividad_Relacionada": "Sector de Actividad",
        },
        title="Volumen Presupuestario por Sector Económico",
        color_discrete_sequence=PALETA_COLORES,
    )

    # Personalización estética
    fig.update_layout(
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        xaxis_title="Presupuesto Acumulado (€)",
        yaxis_title=None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif"},
        title_font={"size": 16, "color": "#00D2FF"},
    )

    # Formatear etiquetas del eje X en euros legibles
    fig.update_layout(xaxis={"tickformat": ",.0f"})
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Presupuesto: %{x:,.2f} €<extra></extra>",
        marker_line_color="#0F172A",
        marker_line_width=1,
    )

    return fig


def crear_grafico_tarta_origen(df: pd.DataFrame) -> go.Figure:
    """
    Genera un gráfico de sectores (tarta/donut) para mostrar la distribución
    porcentual del presupuesto según el origen geográfico de los fondos.
    """
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Sin datos para mostrar",
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return fig

    # Agrupar datos por ámbito geográfico
    df_agrupado = df.groupby("Ambito_Territorial", as_index=False)["Cuantia"].sum()

    fig = px.pie(
        df_agrupado,
        names="Ambito_Territorial",
        values="Cuantia",
        hole=0.4,
        title="Distribución del Gasto por Ámbito Territorial",
        color_discrete_sequence=PALETA_COLORES,
    )

    # Personalización estética y leyendas
    fig.update_layout(
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif"},
        title_font={"size": 16, "color": "#00D2FF"},
    )

    fig.update_traces(
        textinfo="percent+label",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Presupuesto: %{value:,.2f} €<br>"
            "Porcentaje: %{percent}<extra></extra>"
        ),
    )

    return fig
