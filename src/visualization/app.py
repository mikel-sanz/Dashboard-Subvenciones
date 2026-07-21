# ruff: noqa: E402, I001
"""
Orquestador Principal del Dashboard Streamlit.

Este módulo inicializa el dashboard, realiza una ingesta automática al primer arranque
si no hay datos persistidos, aplica los filtros dinámicos, muestra alertas en caso de
datos simulados, y renderiza los componentes de visualización interactiva.
"""

import datetime
import logging
import sys
import threading
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
from src.storage.database import DatabaseManager
from src.storage.models import UsuarioDB
from src.storage.db_session import DBSession
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
session = DBSession.get_session()
try:
    db_users = session.query(UsuarioDB).all()
    credentials = {
        "usernames": {
            u.username.lower(): {
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
    cookie_name="moriarty_session_v2",
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

# Validar que el usuario que dice estar autenticado realmente existe en la base de datos
username_activo = st.session_state["username"]
if username_activo not in credentials["usernames"]:
    # Forzar el logout y limpiar cookies/sesión
    authenticator.logout("Cerrar Sesión", "sidebar")
    st.session_state["authentication_status"] = None
    st.session_state["username"] = None
    st.warning(
        "Tu sesión ha expirado o el usuario ya no existe en la base de "
        "datos. Por favor inicia sesión de nuevo."
    )
    st.rerun()

# Registrar log de auditoría del inicio de sesión (una vez por sesión)
if "auditoria_login_registrada" not in st.session_state:
    db_manager.registrar_evento_auditoria(
        username=username_activo,
        accion="Inicio de Sesión",
        detalles="El usuario ha accedido con éxito a la aplicación.",
    )
    st.session_state["auditoria_login_registrada"] = True

# Añadir botón de logout en el panel lateral
authenticator.logout("Cerrar Sesión", "sidebar")

# --- 1. INICIALIZACIÓN DEL SCHEDULER ASÍNCRONO (SINGLETON SEGURO) ---
if "scheduler_iniciado" not in st.session_state:
    from src.ingestion.scheduler import IngestionScheduler
    scheduler_inst = IngestionScheduler(db_manager)
    scheduler_inst.start()
    st.session_state["scheduler_iniciado"] = True

# --- 2. MECANISMO DE FALLBACK AUTOMÁTICO POR TIEMPO TRANSCURRIDO ---
if "refresco_inicial_verificado" not in st.session_state:
    session_audit = DBSession.get_session()
    from src.storage.models import LogAuditoriaDB
    try:
        # Buscar la última acción de ingesta exitosa
        ultimo_log = (
            session_audit.query(LogAuditoriaDB)
            .filter(
                LogAuditoriaDB.accion.in_(
                    [
                        "Ingesta de Datos (Scheduler)",
                        "Ingesta de Datos (Manual)",
                        "Inicio de Ingesta",
                    ]
                )
            )
            .order_by(LogAuditoriaDB.fecha_hora.desc())
            .first()
        )

        ejecutar_refresco = False
        if not ultimo_log:
            ejecutar_refresco = True
        else:
            diferencia = datetime.datetime.utcnow() - ultimo_log.fecha_hora
            if diferencia.total_seconds() > (
                settings.AUTO_REFRESH_THRESHOLD_HOURS * 3600
            ):
                ejecutar_refresco = True

        if ejecutar_refresco:
            logger.info(
                "El refresco programado no se ejecutó en las últimas 24h. "
                "Lanzando actualización automática de fallback..."
            )
            from src.ingestion.scheduler import IngestionScheduler
            scheduler_temp = IngestionScheduler(db_manager)
            threading.Thread(
                target=scheduler_temp.ejecutar_ingesta_y_notificar,
                daemon=True,
            ).start()
    except Exception as exc:
        logger.error(
            f"Error al verificar refresco automático de fallback: {exc}"
        )
    finally:
        session_audit.close()
    st.session_state["refresco_inicial_verificado"] = True


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

engine_url_str = str(DBSession.get_engine().url)
if "postgres" in settings.DATABASE_URL and "sqlite" in engine_url_str:
    st.warning(
        "⚠️ **Aviso de Persistencia**: La aplicación no pudo conectarse a la "
        "base de datos PostgreSQL externa configurada. Se ha activado el "
        "almacenamiento local SQLite como fallback. Los datos y usuarios "
        "creados podrían borrarse al reiniciarse el contenedor en la nube."
    )

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

    # Filtro por Estado de Vigencia (En plazo / Fuera de plazo)
    if not df_filtrado.empty:
        hoy = datetime.date.today()
        if filtros["estado_vigencia"] == "Solo Vigentes / Activas (En plazo)":
            df_filtrado = df_filtrado[df_filtrado["Fecha_Vigencia"] >= hoy]
        elif filtros["estado_vigencia"] == "Solo Expiradas (Fuera de plazo)":
            df_filtrado = df_filtrado[df_filtrado["Fecha_Vigencia"] < hoy]

    # Filtro por Rango de Fechas de Vigencia
    if not df_filtrado.empty:
        df_filtrado = df_filtrado[
            (df_filtrado["Fecha_Vigencia"] >= filtros["fecha_inicio"])
            & (df_filtrado["Fecha_Vigencia"] <= filtros["fecha_fin"])
        ]

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

        # Mapear los importes 0.0 a un texto explicativo para el visor
        df_visor["Presupuesto"] = df_visor["Cuantia"].apply(
            lambda x: f"{x:,.2f} €" if x > 0.0 else "Consultar bases oficiales"
        )

        df_visor_render = df_visor[
            [
                "Tipo_Subvencion",
                "Presupuesto",
                "Fecha_Vigencia",
                "Entidad_Convocante",
                "Ambito_Territorial",
                "Actividad_Relacionada",
                "URL_Convocatoria",
            ]
        ]

        # Las filas sin URL se muestran con campo vacío (no enlace roto)
        st.dataframe(
            df_visor_render,
            width="stretch",
            column_config={
                "Tipo_Subvencion": st.column_config.TextColumn(
                    "Convocatoria / Línea de Ayuda"
                ),
                "Presupuesto": st.column_config.TextColumn(
                    "Presupuesto"
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

    # --- 9. EXPORTACIÓN DE INFORMES ---
    if not df_filtrado.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<h3 style='color:#012A4A; font-family:sans-serif;'>"
            "Exportar Informes</h3>",
            unsafe_allow_html=True,
        )
        st.write(
            "Descarga los datos filtrados en formato corporativo "
            "para compartirlos con tu equipo o incluirlos en "
            "documentación oficial."
        )

        from src.visualization.reports import ReportExporter

        col_excel, col_pdf = st.columns(2)

        with col_excel:
            excel_bytes = ReportExporter.generar_excel(
                df_filtrado
            )
            st.download_button(
                label="📥 Descargar Excel (.xlsx)",
                data=excel_bytes,
                file_name="informe_subvenciones.xlsx",
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                key="btn_download_excel",
            )

        with col_pdf:
            pdf_bytes = ReportExporter.generar_pdf(
                df_filtrado
            )
            st.download_button(
                label="📄 Descargar PDF",
                data=pdf_bytes,
                file_name="informe_subvenciones.pdf",
                mime="application/pdf",
                key="btn_download_pdf",
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
                # Disparamos la ingesta manual que incluye el triggering de alertas
                from src.ingestion.scheduler import IngestionScheduler
                scheduler_temp = IngestionScheduler(db_manager)
                scheduler_temp.ejecutar_ingesta_y_notificar()

                # Purgamos la caché de datos de Streamlit para obligar recarga de DB
                st.cache_data.clear()

                # Registrar el evento en logs de auditoría
                db_manager.registrar_evento_auditoria(
                    username=username_activo,
                    accion="Ingesta de Datos (Manual)",
                    detalles="Sincronización manual forzada de APIs en vivo.",
                )
                st.success(
                    "¡Ingesta finalizada, alertas enviadas y caché "
                    "actualizada con éxito!"
                )
                # Forzar recarga automática de la UI para mostrar datos nuevos
                st.rerun()
            except Exception as exc:
                st.error(f"Fallo durante la sincronización manual: {exc}")

    # Acción 2: Estado del Clasificador Semántico NLP
    st.markdown("### Estado del Clasificador Semántico (NLP)")
    from src.processing.classifier import SemanticClassifier

    if not settings.USE_SEMANTIC_CLASSIFIER:
        st.info(
            "ℹ️ **Heurística Clásica Activa**: La clasificación "
            "semántica NLP está desactivada por configuración global."
        )
    elif SemanticClassifier._usar_fallback:
        st.warning(
            "⚠️ **Heurística Clásica (Modo Resiliencia)**: El clasificador "
            "NLP local no pudo inicializarse (falta de memoria o de recursos "
            "de red). Se ha activado el fallback a palabras clave de forma "
            "automática."
        )
    elif SemanticClassifier._pipeline is not None:
        st.success(
            f"🟢 **NLP Semántico Activo**: Modelo `{settings.NLP_MODEL_NAME}` "
            "cargado correctamente en memoria y precalculando embeddings "
            "de sectores."
        )
    else:
        st.info(
            f"⏳ **NLP Semántico Inicializado**: El modelo `{settings.NLP_MODEL_NAME}` "
            "se cargará de forma perezosa al realizar la primera ingesta."
        )

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
            ).strip().upper()
            nuevo_email = st.text_input(
                "Correo electrónico:",
                help="Ejemplo: usuario@correo.com",
            ).strip().lower()
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

    st.markdown("---")
    st.markdown("### 🔔 Configuración de Preferencias de Alertas por Email")
    st.write(
        "Activa o desactiva las notificaciones por correo electrónico "
        "y define qué tipo de subvenciones deseas vigilar."
    )

    # Buscar en base de datos las preferencias del usuario actual
    session = DBSession.get_session()
    user_db = (
        session.query(UsuarioDB)
        .filter(UsuarioDB.username == username_activo)
        .first()
    )

    recibir_alertas_val = False
    sectores_val = "*"
    ambitos_val = "*"

    if user_db:
        recibir_alertas_val = user_db.recibir_alertas
        sectores_val = user_db.sectores_interes
        ambitos_val = user_db.ambitos_interes
    session.close()

    # Definir opciones para los selectores multiselect
    SECTORES_OPCIONES = [
        "Digitalización/Robótica",
        "Transición Verde/Sostenibilidad",
        "Agroalimentario",
        "Educación/Social",
        "I+D+i Científica",
        "Emprendimiento/Startups"
    ]
    AMBITOS_OPCIONES = ["Europa", "España", "Navarra", "Pamplona"]

    # Procesar defaults
    default_sectores = (
        SECTORES_OPCIONES
        if sectores_val == "*"
        else [s.strip() for s in sectores_val.split(",") if s.strip()]
    )
    default_ambitos = (
        AMBITOS_OPCIONES
        if ambitos_val == "*"
        else [a.strip() for a in ambitos_val.split(",") if a.strip()]
    )

    # Formulario de preferencias
    help_recibir = (
        "Las notificaciones se enviarán al correo electrónico registrado "
        "en tu perfil."
    )
    help_sectores = (
        "Recibirás alertas únicamente para los sectores seleccionados."
    )
    help_ambitos = (
        "Recibirás alertas únicamente para los ámbitos territoriales "
        "seleccionados."
    )

    with st.form("form_preferencias_alertas"):
        col_recibir, _ = st.columns([2, 1])
        with col_recibir:
            recibir = st.checkbox(
                "Deseo recibir correos automáticos al detectarse nuevas subvenciones",
                value=recibir_alertas_val,
                help=help_recibir,
            )

        col_sectores, col_ambitos = st.columns(2)
        with col_sectores:
            sectores_sel = st.multiselect(
                "Filtrar por sectores de actividad:",
                options=SECTORES_OPCIONES,
                default=default_sectores,
                help=help_sectores,
            )
        with col_ambitos:
            ambitos_sel = st.multiselect(
                "Filtrar por ámbito geográfico:",
                options=AMBITOS_OPCIONES,
                default=default_ambitos,
                help=help_ambitos,
            )

        boton_guardar_pref = st.form_submit_button("💾 Guardar Preferencias de Alertas")

        if boton_guardar_pref:
            # Si se seleccionaron todos los elementos, guardamos "*" para simplificar
            sectores_str = (
                "*"
                if len(sectores_sel) == len(SECTORES_OPCIONES) or not sectores_sel
                else ",".join(sectores_sel)
            )
            ambitos_str = (
                "*"
                if len(ambitos_sel) == len(AMBITOS_OPCIONES) or not ambitos_sel
                else ",".join(ambitos_sel)
            )

            exito, err_msg = db_manager.actualizar_preferencias_alertas(
                username=username_activo,
                recibir=recibir,
                sectores=sectores_str,
                ambitos=ambitos_str
            )

            if exito:
                db_manager.registrar_evento_auditoria(
                    username=username_activo,
                    accion="Modificación de Preferencias de Alertas",
                    detalles=(
                        f"Alertas: {recibir}, Sectores: '{sectores_str}', "
                        f"Ámbitos: '{ambitos_str}'"
                    )
                )
                st.success("¡Tus preferencias de alertas se han guardado con éxito!")
                st.rerun()
            else:
                st.error(
                    f"Ocurrió un error al persistir tus preferencias: {err_msg}"
                )
