# ruff: noqa: E402, I001
"""
Orquestador Principal del Dashboard Streamlit.

Este módulo inicializa el dashboard, realiza una ingesta automática al primer arranque
si no hay datos persistidos, aplica los filtros dinámicos, muestra alertas en caso de
datos simulados, y renderiza los componentes de visualización interactiva.
"""

import logging
import sys
from pathlib import Path

# Añadir el directorio raíz del proyecto al sys.path para importaciones absolutas
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth

from src.config import settings
from src.ingestion.espana_bdns import EspanaBdnsExtractor
from src.ingestion.europa_funding import EuropaFundingExtractor
from src.ingestion.navarra_ckan import NavarraCkanExtractor
from src.processing.normalizer import Normalizer
import importlib
import src.storage.database
importlib.reload(src.storage.database)
from src.storage.database import DatabaseManager, UsuarioDB
from src.visualization.charts import (
    crear_grafico_barras_actividad,
    crear_grafico_tarta_origen,
)
from src.visualization.components import render_kpi_metrics, render_sidebar_filters

# Configuración básica de logs para la aplicación
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuración de página de Streamlit (SEO y Layout)
st.set_page_config(
    page_title="Dashboard Automatizado de Subvenciones (Europa - España - Navarra)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Inicialización del gestor de persistencia
db_manager = DatabaseManager(settings.DATABASE_URL)

# --- 0. CAPA DE AUTENTICACIÓN ---
session = db_manager.SessionLocal()
try:
    db_users = session.query(UsuarioDB).all()
    credentials = {
        "usernames": {
            u.username: {
                "email": u.email,
                "name": u.username,
                "password": u.password_hash,
            }
            for u in db_users
        }
    }
finally:
    session.close()

authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="subvenciones_dashboard_cookie",
    key=settings.JWT_SECRET,
    cookie_expiry_days=settings.COOKIE_EXPIRY_DAYS,
)

# Dibujar pantalla de login
authenticator.login()

if st.session_state["authentication_status"] is False:
    st.error("Nombre de usuario o contraseña incorrectos.")
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.info("Introduce tus credenciales para acceder al dashboard.")
    st.stop()

# Registrar log de auditoría del inicio de sesión (una vez por sesión)
username_activo = st.session_state["username"]
if "auditoria_login_registrada" not in st.session_state:
    db_manager.registrar_evento_auditoria(
        username=username_activo,
        accion="Inicio de Sesión",
        detalles="El usuario ha accedido con éxito a la aplicación.",
    )
    st.session_state["auditoria_login_registrada"] = True

# Añadir botón de logout en el panel lateral
authenticator.logout("Cerrar Sesión", "sidebar")


def ejecutar_ingesta_inicial() -> None:
    """
    Ejecuta el pipeline completo de ingesta y persistencia inicial de forma automática.

    Se activa si se detecta que la base de datos de subvenciones está vacía al arrancar.
    """
    logger.info("Base de datos vacía detectada. Iniciando ingesta automática...")

    # 1. Instanciamos los tres extractores
    extractores = [
        NavarraCkanExtractor(),
        EspanaBdnsExtractor(),
        EuropaFundingExtractor(),
    ]

    registros_crudos = []
    for ext in extractores:
        try:
            # Cada extractor aplica internamente sus reintentos y fallback a simulados
            registros_crudos.extend(ext.extract())
        except Exception as exc:
            logger.error(f"Error crítico al extraer datos de {ext.name}: {exc}")

    # 2. Normalizamos y validamos mediante Pydantic
    subvenciones_validadas = Normalizer.normalizar_lote(registros_crudos)

    # 3. Guardamos los datos normalizados en la base de datos
    db_manager.bulk_insert(subvenciones_validadas)
    logger.info("Ingesta automática de arranque finalizada con éxito.")


@st.cache_data(ttl=3600)
def cargar_datos_cached() -> pd.DataFrame:
    """
    Carga los datos desde la base de datos persistida y aplica caché para rendimiento.
    """
    # Si la base de datos está vacía, realizamos la ingesta automática primero
    df_temp = db_manager.load_as_dataframe()
    if df_temp.empty:
        ejecutar_ingesta_inicial()
        df_temp = db_manager.load_as_dataframe()
    return df_temp


# --- 1. CARGA DE DATOS ---
df_original = cargar_datos_cached()

st.markdown(
    "<h1 id='title-main' style='color:#012A4A; font-family:sans-serif; "
    "text-align:center; margin-bottom:10px;'>"
    "Dashboard Automatizado de Subvenciones Públicas"
    "</h1>"
    "<p style='text-align:center; color:#5D6D7E; font-size:1.1em; "
    "margin-bottom:30px;'>"
    "Monitoreo en tiempo real de fondos presupuestarios de la Unión "
    "Europea, el Estado Español y Navarra."
    "</p>",
    unsafe_allow_html=True,
)

# --- 2. CREACIÓN DE PESTAÑAS (TABS) ---
tab_dashboard, tab_admin, tab_users = st.tabs(
    [
        "📈 Dashboard de Subvenciones",
        "⚙️ Administración y Auditoría",
        "👥 Gestión de Usuarios",
    ]
)

with tab_dashboard:
    # --- 4. PANEL LATERAL DE FILTROS ---
    filtros = render_sidebar_filters(df_original)

    # --- 5. APLICACIÓN DE FILTROS DINÁMICOS ---
    df_filtrado = df_original.copy()

    if filtros["ambitos"]:
        df_filtrado = df_filtrado[
            df_filtrado["Ambito_Territorial"].isin(filtros["ambitos"])
        ]
    else:
        df_filtrado = df_filtrado.iloc[0:0]

    if filtros["sectores"] and not df_filtrado.empty:
        df_filtrado = df_filtrado[
            df_filtrado["Actividad_Relacionada"].isin(filtros["sectores"])
        ]
    else:
        if not filtros["sectores"]:
            df_filtrado = df_filtrado.iloc[0:0]

    # --- 3. DETECCIÓN Y SEÑALIZACIÓN DE DATOS SIMULADOS (REQUISITO CRÍTICO) ---
    # Solo mostramos advertencia si los datos en pantalla contienen fallback
    if not df_filtrado.empty and df_filtrado["Es_Simulado"].any():
        ambitos_simulados = (
            df_filtrado[df_filtrado["Es_Simulado"]]["Ambito_Territorial"]
            .unique()
            .tolist()
        )

        mensaje_alerta = (
            "⚠️ **Atención**: Se están visualizando **datos simulados de prueba "
            f"(fallback)** para los ámbitos geográficos: "
            f"**{', '.join(ambitos_simulados)}**. Esto ocurre debido a la "
            "indisponibilidad de conexión o restricciones de red temporales "
            "con las APIs públicas de las fuentes oficiales."
        )
        st.warning(mensaje_alerta)

    # --- 6. RENDERIZACIÓN DE METRICAS KPI ---
    render_kpi_metrics(df_filtrado)
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 7. RENDERIZACIÓN DE GRÁFICOS INTERACTIVOS ---
    col_barras, col_tarta = st.columns(2)

    with col_barras:
        fig_barras = crear_grafico_barras_actividad(df_filtrado)
        st.plotly_chart(
            fig_barras, width="stretch", key="chart_barras"
        )

    with col_tarta:
        fig_tarta = crear_grafico_tarta_origen(df_filtrado)
        st.plotly_chart(
            fig_tarta, width="stretch", key="chart_tarta"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 8. VISOR DE DATOS CON ENLACES A FUENTES OFICIALES ---
    st.markdown(
        "<h3 style='color:#012A4A; font-family:sans-serif;'>"
        "Visor Detallado de Convocatorias</h3>",
        unsafe_allow_html=True,
    )

    if not df_filtrado.empty:
        # Preparar DataFrame para visualización con enlaces
        df_visor = df_filtrado[
            [
                "Tipo_Subvencion",
                "Cuantia",
                "Fecha_Vigencia",
                "Entidad_Convocante",
                "Ambito_Territorial",
                "Actividad_Relacionada",
                "URL_Convocatoria",
            ]
        ].sort_values(by="Cuantia", ascending=False).copy()

        # Las filas sin URL se muestran con campo vacío (no enlace roto)
        st.dataframe(
            df_visor,
            width="stretch",
            column_config={
                "Tipo_Subvencion": st.column_config.TextColumn(
                    "Convocatoria / Línea de Ayuda"
                ),
                "Cuantia": st.column_config.NumberColumn(
                    "Presupuesto (€)", format="%.2f €"
                ),
                "Fecha_Vigencia": st.column_config.DateColumn(
                    "Fecha Límite / Vigencia"
                ),
                "Entidad_Convocante": st.column_config.TextColumn(
                    "Entidad Convocante"
                ),
                "Ambito_Territorial": st.column_config.TextColumn(
                    "Ámbito Territorial"
                ),
                "Actividad_Relacionada": st.column_config.TextColumn(
                    "Actividad Relacionada"
                ),
                "URL_Convocatoria": st.column_config.LinkColumn(
                    "🔗 Ficha Oficial",
                    display_text="Ver convocatoria",
                ),
            },
        )
    else:
        st.info(
            "No hay registros que coincidan con "
            "los filtros del sidebar."
        )

with tab_admin:
    st.markdown(
        "<h2 style='color:#012A4A; font-family:sans-serif;'>"
        "Consola de Administración y Auditoría</h2>",
        unsafe_allow_html=True,
    )

    # Acción 1: Ingesta manual en vivo
    st.markdown("### Actualización de Datos en Tiempo Real")
    st.write(
        "Fuerza una conexión en caliente a las APIs oficiales de Europa, "
        "España y Navarra para obtener las últimas convocatorias "
        "y actualizar la persistencia en la base de datos."
    )

    if st.button("🔄 Ejecutar Ingesta Manual (APIs en Vivo)"):
        with st.spinner("Conectando con las APIs y actualizando registros..."):
            try:
                # Disparamos la ingesta manual
                ejecutar_ingesta_inicial()
                # Purgamos la caché de datos de Streamlit para obligar recarga de DB
                st.cache_data.clear()
                # Registrar el evento en logs de auditoría
                db_manager.registrar_evento_auditoria(
                    username=username_activo,
                    accion="Ingesta Manual",
                    detalles="Ejecución forzada de sincronización de APIs en vivo.",
                )
                st.success(
                    "¡Ingesta de datos finalizada y caché de consultas actualizada!"
                )
                # Forzar recarga automática de la UI para mostrar datos nuevos
                st.rerun()
            except Exception as exc:
                st.error(f"Fallo durante la sincronización manual: {exc}")

    st.markdown("<br><hr>", unsafe_allow_html=True)

    # Acción 2: Visualización de logs de auditoría
    st.markdown("### Historial de Auditoría de Actividad")
    st.write(
        "Últimos 100 eventos interactivos registrados en la plataforma. "
        "Permite trazar cuándo y quién realiza consultas y operaciones."
    )

    df_logs = db_manager.obtener_logs_auditoria(100)
    if not df_logs.empty:
        st.dataframe(
            df_logs,
            width="stretch",
            column_config={
                "fecha_hora": st.column_config.DatetimeColumn(
                    "Fecha y Hora (UTC)", format="DD/MM/YYYY HH:mm:ss"
                ),
                "username": st.column_config.TextColumn("Usuario"),
                "accion": st.column_config.TextColumn("Operación"),
                "detalles": st.column_config.TextColumn("Detalles de Actividad"),
            },
        )
    else:
        st.info("No se han registrado eventos de auditoría en la base de datos.")

with tab_users:
    st.markdown(
        "<h2 style='color:#012A4A; font-family:sans-serif;'>"
        "Gestión de Acceso de Usuarios</h2>",
        unsafe_allow_html=True,
    )

    col_alta, col_cambio, col_baja = st.columns(3)

    with col_alta:
        st.markdown("### Registrar Nuevo Usuario")
        with st.form("form_alta_usuario", clear_on_submit=True):
            nuevo_username = st.text_input(
                "Nombre de usuario:",
                help="Debe ser único en el sistema.",
            ).strip()
            nuevo_email = st.text_input(
                "Correo electrónico:",
                help="Ejemplo: usuario@correo.com",
            ).strip()
            nueva_contrasena = st.text_input(
                "Contraseña:",
                type="password",
                help="Contraseña para acceder a la aplicación.",
            )
            boton_alta = st.form_submit_button("Crear Usuario")

            if boton_alta:
                if (
                    not nuevo_username
                    or not nuevo_email
                    or not nueva_contrasena
                ):
                    st.error("Por favor, rellene todos los campos.")
                elif "@" not in nuevo_email or "." not in nuevo_email:
                    st.error("Formato de correo electrónico inválido.")
                else:
                    exito = db_manager.crear_usuario(
                        username=nuevo_username,
                        email=nuevo_email,
                        contrasena_plana=nueva_contrasena,
                    )
                    if exito:
                        db_manager.registrar_evento_auditoria(
                            username=username_activo,
                            accion="Alta de Usuario",
                            detalles=(
                                f"Se creó con éxito al usuario "
                                f"'{nuevo_username}' con email "
                                f"'{nuevo_email}'."
                            ),
                        )
                        st.success(
                            f"¡Usuario '{nuevo_username}' creado!"
                        )
                        st.rerun()
                    else:
                        st.error(
                            f"Fallo al registrar usuario. El "
                            f"username '{nuevo_username}' podría estar "
                            f"duplicado."
                        )

    # Obtener lista fresca de usuarios de la base de datos
    usuarios = db_manager.obtener_usuarios()

    with col_cambio:
        st.markdown("### Cambiar Contraseña")
        st.write(
            "Permite actualizar la contraseña de acceso de cualquier "
            "usuario existente en el sistema de forma segura."
        )

        nombres_todos = [u.username for u in usuarios]
        if nombres_todos:
            with st.form("form_cambio_contrasena", clear_on_submit=True):
                user_seleccionado = st.selectbox(
                    "Seleccionar usuario:",
                    options=nombres_todos,
                )
                contrasena_nueva = st.text_input(
                    "Nueva contraseña:",
                    type="password",
                    help="Introduzca la nueva contraseña del usuario.",
                )
                boton_cambio = st.form_submit_button(
                    "Actualizar Contraseña"
                )

                if boton_cambio:
                    if not contrasena_nueva:
                        st.error("Por favor, introduzca la contraseña.")
                    elif len(contrasena_nueva) < 4:
                        st.error("La contraseña debe tener al menos 4 caracteres.")
                    else:
                        exito = db_manager.actualizar_contrasena(
                            username=user_seleccionado,
                            nueva_contrasena_plana=contrasena_nueva,
                        )
                        if exito:
                            db_manager.registrar_evento_auditoria(
                                username=username_activo,
                                accion="Cambio de Contraseña",
                                detalles=(
                                    f"Se actualizó la contraseña del "
                                    f"usuario '{user_seleccionado}'."
                                ),
                            )
                            st.success("¡Contraseña actualizada!")
                            st.rerun()
                        else:
                            st.error("Error al actualizar la contraseña.")
        else:
            st.info("No hay usuarios registrados en el sistema.")

    with col_baja:
        st.markdown("### Eliminar Usuario")
        st.write(
            "Seleccione un usuario de la lista para darlo de baja del "
            "sistema de forma permanente."
        )

        # Excluir al usuario actual para evitar auto-eliminación
        nombres_baja = [
            u.username for u in usuarios if u.username != username_activo
        ]

        if nombres_baja:
            usuario_a_eliminar = st.selectbox(
                "Seleccionar usuario para dar de baja:",
                options=nombres_baja,
            )

            # Confirmación adicional para seguridad
            confirmar_baja = st.checkbox(
                f"Confirmar baja de '{usuario_a_eliminar}'"
            )

            if st.button("❌ Dar de Baja Usuario", type="primary"):
                if not confirmar_baja:
                    st.warning("Marque la casilla de confirmación.")
                else:
                    exito = db_manager.eliminar_usuario(usuario_a_eliminar)
                    if exito:
                        db_manager.registrar_evento_auditoria(
                            username=username_activo,
                            accion="Baja de Usuario",
                            detalles=(
                                f"Se eliminó con éxito al usuario "
                                f"'{usuario_a_eliminar}'."
                            ),
                        )
                        st.success(
                            f"¡Usuario '{usuario_a_eliminar}' eliminado!"
                        )
                        st.rerun()
                    else:
                        st.error(
                            "No se pudo eliminar al usuario."
                        )
        else:
            st.info("No hay otros usuarios registrados para dar de baja.")
