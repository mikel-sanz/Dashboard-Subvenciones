"""
🛡️ NEXO MDU: scheduler.py
Propósito: Gestor del programador de ingesta de datos asíncrona de fondo y alertas.
Arquitectura: Modular Design Unit (MDU) - Capa de Servicios y Ingesta.
Licencia: Propietaria NEXO Ecosystem.
"""

import logging
from typing import List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings
from src.ingestion.espana_bdns import EspanaBdnsExtractor
from src.ingestion.europa_funding import EuropaFundingExtractor
from src.ingestion.cordis_extractor import CordisExtractor
from src.ingestion.ted_extractor import TedExtractor
from src.ingestion.navarra_ckan import NavarraCkanExtractor
from src.ingestion.pamplona_extractor import PamplonaExtractor
from src.notifications.alerts import EmailNotifier
from src.processing.normalizer import Normalizer
from src.processing.schemas import SubvencionSchema
from src.storage.database import DatabaseManager
from src.storage.models import UsuarioDB
from src.storage.db_session import DBSession

# Configuración de logging local
logger = logging.getLogger(__name__)


class IngestionScheduler:
    """
    Gestiona el programador asíncrono en segundo plano para ejecutar
    periódicamente la ingesta de APIs públicas, normalización y alertas.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self.notifier = EmailNotifier()
        # Inicializar scheduler como daemon para no bloquear la salida de Python
        self.scheduler = BackgroundScheduler(daemon=True)

    def ejecutar_ingesta_y_notificar(self) -> None:
        """
        Ejecuta la ingesta automática periódica de las tres APIs públicas,
        realiza el bulk insert deduplicado y notifica a los usuarios suscritos
        si se detectan nuevas subvenciones.
        """
        logger.info("Iniciando ciclo automático de ingesta asíncrona...")

        extractores = [
            NavarraCkanExtractor(),
            EspanaBdnsExtractor(),
            EuropaFundingExtractor(),
            PamplonaExtractor(),
            CordisExtractor(),
            TedExtractor(),
        ]

        registros_crudos = []
        for ext in extractores:
            try:
                registros_crudos.extend(ext.extract())
            except Exception as exc:
                logger.error(
                    f"Error al extraer datos desde {ext.__class__.__name__}: "
                    f"{exc}"
                )

        if not registros_crudos:
            logger.info("No se han recuperado registros en este ciclo.")
            return

        # Normalizar lote completo
        subvenciones_validadas = Normalizer.normalizar_lote(registros_crudos)

        # Insertar de forma segura en la base de datos
        nuevos_persistidos_cnt = self.db_manager.bulk_insert(
            subvenciones_validadas
        )
        logger.info(
            f"Ciclo de ingesta finalizado. Nuevas subvenciones añadidas: "
            f"{nuevos_persistidos_cnt}"
        )

        # Si hay nuevos registros insertados, procedemos a distribuir las alertas
        if nuevos_persistidos_cnt > 0:
            # Recuperar las últimas N subvenciones insertadas
            nuevos_registros = subvenciones_validadas[-nuevos_persistidos_cnt:]
            self.distribuir_alertas(nuevos_registros)

            # Registrar evento en auditoría
            self.db_manager.registrar_evento_auditoria(
                username="SYSTEM",
                accion="Ingesta de Datos (Scheduler)",
                detalles=(
                    f"Actualización automática exitosa. "
                    f"Se añadieron {nuevos_persistidos_cnt} nuevas subvenciones."
                ),
            )

    def distribuir_alertas(
        self, nuevas_subvenciones: List[SubvencionSchema]
    ) -> None:
        """
        Busca usuarios con alertas activas y envía notificaciones por correo
        si las nuevas subvenciones coinciden con sus intereses.
        """
        session = DBSession.get_session()
        try:
            usuarios_suscritos = (
                session.query(UsuarioDB)
                .filter(UsuarioDB.recibir_alertas == True)
                .all()
            )

            for usuario in usuarios_suscritos:
                subvenciones_usuario = []
                for sub in nuevas_subvenciones:
                    # Comparar sector de forma insensible a mayúsculas y espacios
                    sectores_pref = [
                        s.strip().lower()
                        for s in usuario.sectores_interes.split(",")
                    ]
                    sector_coincide = (
                        usuario.sectores_interes == "*"
                        or sub.Actividad_Relacionada.strip().lower()
                        in sectores_pref
                    )

                    # Comprobación de ámbito geográfico
                    ambitos_pref = [
                        a.strip().lower()
                        for a in usuario.ambitos_interes.split(",")
                    ]
                    ambito_coincide = (
                        usuario.ambitos_interes == "*"
                        or sub.Ambito_Territorial.strip().lower()
                        in ambitos_pref
                    )

                    if sector_coincide and ambito_coincide:
                        subvenciones_usuario.append(sub)

                if subvenciones_usuario:
                    html_cuerpo = self.notifier.construir_plantilla_html(
                        subvenciones_usuario, usuario.username
                    )
                    self.notifier.enviar_correo(
                        destinatario=usuario.email,
                        asunto=(
                            f"Vigilancia MORIARTY: {len(subvenciones_usuario)} "
                            f"Nuevas Ayudas de tu Interés"
                        ),
                        html_content=html_cuerpo,
                    )
        except Exception as exc:
            logger.error(f"Error al distribuir alertas por email: {exc}")
        finally:
            session.close()

    def start(self) -> None:
        """
        Inicia el planificador en segundo plano programado para
        ejecutarse todos los días a la hora configurada (06:00 AM por defecto).
        """
        if not self.scheduler.running:
            # Trigger cron diario a la hora configurada (ej. 6:00 AM)
            self.scheduler.add_job(
                func=self.ejecutar_ingesta_y_notificar,
                trigger=CronTrigger(hour=settings.SCHEDULER_HOUR, minute=0),
                id="job_ingesta_diaria_madrugada",
                replace_existing=True,
            )
            self.scheduler.start()
            logger.info(
                f"Scheduler asíncrono iniciado correctamente. Programado "
                f"diariamente a las {settings.SCHEDULER_HOUR}:00."
            )

    def stop(self) -> None:
        """
        Detiene la ejecución del programador de fondo.
        """
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler asíncrono detenido correctamente.")
