"""
Componentes de UI y Filtros para Streamlit.

Este módulo define las métricas clave del negocio y el panel de filtros
del sidebar para la interacción del usuario en el dashboard.
"""

import datetime
from typing import Any

import pandas as pd
import streamlit as st


def render_sidebar_filters(df: pd.DataFrame) -> dict[str, Any]:
    """
    Dibuja los selectores en el sidebar e inyecta CSS para evitar scroll.
    """
    # Mostrar el logo corporativo Trivium
    st.sidebar.image("imagenes/Trivium.png", use_container_width=True)
    st.sidebar.markdown("<br>", unsafe_allow_html=True)

    st.sidebar.markdown(
        "<h2 style='color:#FFFFFF; font-family:sans-serif;'>Filtros Avanzados</h2>",
        unsafe_allow_html=True,
    )

    # Inyección de CSS para apilar verticalmente los tags y dar contraste
    css_multiselect = """
    <style>
    div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div:first-child {
        max-height: none !important;
        height: auto !important;
        overflow: visible !important;
        flex-direction: column !important;
        align-items: flex-start !important;
    }
    div[data-baseweb="tag"] {
        background-color: #E65F2B !important;
        color: #FFFFFF !important;
        border-radius: 4px !important;
        margin-bottom: 4px !important;
    }
    div[data-baseweb="tag"] span {
        color: #FFFFFF !important;
    }
    </style>
    """
    st.sidebar.markdown(css_multiselect, unsafe_allow_html=True)

    # 1. Filtro por Ámbito Territorial
    ambitos_disponibles = sorted(df["Ambito_Territorial"].unique().tolist())
    ambitos_seleccionados = st.sidebar.multiselect(
        "Ámbito Territorial:",
        options=ambitos_disponibles,
        default=ambitos_disponibles,
        help="Seleccione uno o más niveles geográficos para filtrar.",
    )

    # 2. Filtro por Sector Económico
    sectores_disponibles = sorted(df["Actividad_Relacionada"].unique().tolist())
    sectores_seleccionados = st.sidebar.multiselect(
        "Sector de Actividad:",
        options=sectores_disponibles,
        default=sectores_disponibles,
        help="Seleccione los sectores estratégicos de interés.",
    )

    # 3. Filtro por Estado de Vigencia (Activas / Expiradas)
    estado_vigencia = st.sidebar.selectbox(
        "Estado de Vigencia:",
        options=[
            "Solo Vigentes / Activas (En plazo)",
            "Solo Expiradas (Fuera de plazo)",
            "Todas las convocatorias",
        ],
        index=0,  # Por defecto muestra solo las activas
        help="Filtrar por plazo de presentación de las ayudas.",
    )

    st.sidebar.markdown("**Rango de Fechas (Vigencia):**")
    hoy_ref = datetime.date.today()
    fecha_min = df["Fecha_Vigencia"].min() if not df.empty else hoy_ref
    fecha_max = (
        df["Fecha_Vigencia"].max()
        if not df.empty
        else hoy_ref + datetime.timedelta(days=365)
    )

    rango_fechas = st.sidebar.date_input(
        "Seleccionar rango:",
        value=(fecha_min, fecha_max),
        min_value=fecha_min,
        max_value=fecha_max,
        help="Establezca la ventana de fechas límites de presentación.",
        label_visibility="collapsed",
    )

    # Procesar retorno del rango de fechas de forma robusta
    if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
        fecha_inicio, fecha_fin = rango_fechas
    elif isinstance(rango_fechas, tuple) and len(rango_fechas) == 1:
        fecha_inicio = rango_fechas[0]
        fecha_fin = fecha_max
    else:
        fecha_inicio = fecha_min
        fecha_fin = fecha_max

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<div style='font-size:0.85em; color:gray; text-align:center;'>"
        "Desarrollado para la plataforma de IA de Google.<br>"
        "Proyecto MORIARTY &copy; 2026</div>",
        unsafe_allow_html=True,
    )

    return {
        "ambitos": ambitos_seleccionados,
        "sectores": sectores_seleccionados,
        "estado_vigencia": estado_vigencia,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
    }


def render_kpi_metrics(df: pd.DataFrame) -> None:
    """
    Renderiza los KPI blocks de rendimiento y volumen económico.

    Muestra el Presupuesto Total Analizado y la cantidad de convocatorias vigentes.
    """
    # 1. Calcular Presupuesto Total
    presupuesto_total = df["Cuantia"].sum() if not df.empty else 0.0

    # 2. Calcular Convocatorias Activas (vigencia futura o igual al día de hoy)
    hoy = datetime.date.today()
    lineas_activas_cnt = df[df["Fecha_Vigencia"] >= hoy].shape[0] if not df.empty else 0

    # Renderizado en columnas con CSS para crear un aspecto premium de tarjetas
    col1, col2 = st.columns(2)

    with col1:
        card1_html = (
            "<div style='background-color:#EBF5FB; border-left:5px solid #2A6F97; "
            "padding:15px; border-radius:8px; "
            "box-shadow: 0 4px 6px rgba(0,0,0,0.05);'>"
            "<p style='margin:0; font-size:0.9em; color:#014F86; "
            "font-weight:bold;'>PRESUPUESTO TOTAL ANALIZADO</p>"
            "<p style='margin:5px 0 0 0; font-size:1.8em; "
            f"font-weight:bold; color:#012A4A;'>{presupuesto_total:,.2f} €</p>"
            "</div>"
        )
        st.markdown(card1_html, unsafe_allow_html=True)

    with col2:
        card2_html = (
            "<div style='background-color:#EAF2F8; border-left:5px solid #014F86; "
            "padding:15px; border-radius:8px; "
            "box-shadow: 0 4px 6px rgba(0,0,0,0.05);'>"
            "<p style='margin:0; font-size:0.9em; color:#014F86; "
            "font-weight:bold;'>CONVOCATORIAS ACTIVAS VIGENTES</p>"
            "<p style='margin:5px 0 0 0; font-size:1.8em; "
            f"font-weight:bold; color:#012A4A;'>{lineas_activas_cnt} Líneas</p>"
            "</div>"
        )
        st.markdown(card2_html, unsafe_allow_html=True)
