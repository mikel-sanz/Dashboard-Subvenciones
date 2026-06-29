"""
🛡️ NEXO MDU: reports.py
Propósito: Generador de informes corporativos en PDF y Excel en memoria.
Arquitectura: Modular Design Unit (MDU) - Capa de Presentación.
"""

import datetime
import io
import logging
from typing import List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Paleta corporativa del dashboard
COLOR_CORPORATIVO_HEX = "012A4A"
COLOR_CABECERA_RGB = (1, 42, 74)
COLOR_TEXTO_BLANCO_RGB = (255, 255, 255)


class ReportExporter:
    """
    Genera informes exportables (Excel y PDF) a partir de los datos
    filtrados del dashboard. Todos los métodos operan en memoria
    (BytesIO) para evitar escritura en disco en entornos cloud.
    """

    @staticmethod
    def generar_excel(df: pd.DataFrame) -> bytes:
        """
        Genera un archivo Excel (.xlsx) corporativo en memoria.

        Args:
            df: DataFrame con los datos filtrados del dashboard.

        Returns:
            bytes: Contenido binario del archivo Excel.

        Ejemplo:
            >>> datos = ReportExporter.generar_excel(df_filtrado)
            >>> len(datos) > 0
            True
        """
        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            # --- Hoja 1: Resumen KPI ---
            resumen = _construir_resumen_kpi(df)
            resumen.to_excel(
                writer, sheet_name="Resumen KPI", index=False
            )

            # --- Hoja 2: Datos Detallados ---
            columnas_exportar = [
                col for col in [
                    "Tipo_Subvencion",
                    "Cuantia",
                    "Fecha_Vigencia",
                    "Entidad_Convocante",
                    "Ambito_Territorial",
                    "Actividad_Relacionada",
                    "URL_Convocatoria",
                ] if col in df.columns
            ]
            if columnas_exportar:
                df_exportar = df[columnas_exportar].copy()
            else:
                df_exportar = df.copy()
            df_exportar.to_excel(
                writer, sheet_name="Convocatorias", index=False
            )

            # --- Aplicar estilos corporativos ---
            _aplicar_estilos_excel(writer)

        buffer.seek(0)
        logger.info(
            f"Informe Excel generado: {len(df)} registros."
        )
        return buffer.getvalue()

    @staticmethod
    def generar_pdf(df: pd.DataFrame) -> bytes:
        """
        Genera un informe PDF corporativo en memoria.

        Args:
            df: DataFrame con los datos filtrados del dashboard.

        Returns:
            bytes: Contenido binario del archivo PDF.

        Ejemplo:
            >>> datos = ReportExporter.generar_pdf(df_filtrado)
            >>> datos[:5] == b'%PDF-'
            True
        """
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
            leftMargin=1 * cm,
            rightMargin=1 * cm,
        )

        styles = getSampleStyleSheet()
        elementos: list = []

        # --- Cabecera ---
        color_corp = colors.Color(
            COLOR_CABECERA_RGB[0] / 255,
            COLOR_CABECERA_RGB[1] / 255,
            COLOR_CABECERA_RGB[2] / 255,
        )
        titulo_style = styles["Title"]
        titulo_style.textColor = color_corp

        elementos.append(
            Paragraph(
                "Informe de Subvenciones Públicas",
                titulo_style,
            )
        )
        fecha_gen = datetime.datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )
        elementos.append(
            Paragraph(
                f"Generado el: {fecha_gen}",
                styles["Normal"],
            )
        )
        elementos.append(Spacer(1, 0.5 * cm))

        # --- Tabla Resumen KPI ---
        resumen_df = _construir_resumen_kpi(df)
        elementos.append(
            Paragraph("Resumen Ejecutivo", styles["Heading2"])
        )
        elementos.append(Spacer(1, 0.3 * cm))

        resumen_data: List[List[str]] = [
            list(resumen_df.columns)
        ]
        for _, fila in resumen_df.iterrows():
            resumen_data.append([str(v) for v in fila.values])

        tabla_resumen = Table(resumen_data)
        tabla_resumen.setStyle(
            TableStyle([
                (
                    "BACKGROUND", (0, 0), (-1, 0),
                    color_corp,
                ),
                (
                    "TEXTCOLOR", (0, 0), (-1, 0),
                    colors.white,
                ),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                (
                    "ROWBACKGROUNDS", (0, 1), (-1, -1),
                    [colors.whitesmoke, colors.white],
                ),
            ])
        )
        elementos.append(tabla_resumen)
        elementos.append(Spacer(1, 0.5 * cm))

        # --- Tabla de Datos Detallados (paginada) ---
        elementos.append(
            Paragraph(
                "Detalle de Convocatorias", styles["Heading2"]
            )
        )
        elementos.append(Spacer(1, 0.3 * cm))

        cols_detalle = _obtener_columnas_detalle(df)
        if df.empty or not cols_detalle:
            elementos.append(
                Paragraph(
                    "No hay convocatorias disponibles que coincidan con los filtros.",
                    styles["Normal"],
                )
            )
        else:
            cabeceras_cortas = _acortar_cabeceras(cols_detalle)
            filas_por_pagina = 40
            total_filas = len(df)

            for inicio in range(0, total_filas, filas_por_pagina):
                bloque = df[cols_detalle].iloc[
                    inicio:inicio + filas_por_pagina
                ]
                datos_tabla: List[List[str]] = [cabeceras_cortas]
                for _, fila in bloque.iterrows():
                    datos_tabla.append(
                        [_truncar(str(v), 45) for v in fila.values]
                    )

                tabla = Table(datos_tabla, repeatRows=1)
                tabla.setStyle(
                    TableStyle([
                        (
                            "BACKGROUND", (0, 0), (-1, 0),
                            color_corp,
                        ),
                        (
                            "TEXTCOLOR", (0, 0), (-1, 0),
                            colors.white,
                        ),
                        (
                            "FONTNAME", (0, 0), (-1, 0),
                            "Helvetica-Bold",
                        ),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        (
                            "GRID", (0, 0), (-1, -1),
                            0.4, colors.grey,
                        ),
                        (
                            "ROWBACKGROUNDS", (0, 1), (-1, -1),
                            [colors.whitesmoke, colors.white],
                        ),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ])
                )
                elementos.append(tabla)
                elementos.append(Spacer(1, 0.3 * cm))

        doc.build(elementos)
        buffer.seek(0)
        logger.info(
            f"Informe PDF generado: {len(df)} registros."
        )
        return buffer.getvalue()


# --- Funciones auxiliares internas ---

def _aplicar_estilos_excel(writer: pd.ExcelWriter) -> None:
    """Aplica estilos corporativos a las cabeceras de cada hoja."""
    from openpyxl.styles import Alignment, Font, PatternFill

    relleno = PatternFill(
        start_color=COLOR_CORPORATIVO_HEX,
        end_color=COLOR_CORPORATIVO_HEX,
        fill_type="solid",
    )
    fuente_blanca = Font(
        color="FFFFFF", bold=True, size=11
    )
    alineacion = Alignment(
        horizontal="center", vertical="center"
    )

    for hoja in writer.sheets.values():
        # Estilizar fila de cabecera
        for celda in hoja[1]:
            celda.fill = relleno
            celda.font = fuente_blanca
            celda.alignment = alineacion

        # Autoajustar ancho de columnas
        for col in hoja.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for celda in col:
                valor = str(celda.value) if celda.value else ""
                max_len = max(max_len, len(valor))
            hoja.column_dimensions[col_letter].width = min(
                max_len + 4, 50
            )

def _construir_resumen_kpi(df: pd.DataFrame) -> pd.DataFrame:
    """Construye un DataFrame de resumen con KPIs agregados."""
    if df.empty:
        return pd.DataFrame({
            "Métrica": ["Total Convocatorias"],
            "Valor": ["0"],
        })

    total = len(df)
    presupuesto = (
        df["Cuantia"].sum() if "Cuantia" in df.columns else 0
    )
    por_ambito: List[Tuple[str, str]] = []
    if "Ambito_Territorial" in df.columns:
        for ambito, count in (
            df["Ambito_Territorial"].value_counts().items()
        ):
            por_ambito.append((f"Ámbito: {ambito}", str(count)))

    por_sector: List[Tuple[str, str]] = []
    if "Actividad_Relacionada" in df.columns:
        for sector, count in (
            df["Actividad_Relacionada"].value_counts().items()
        ):
            por_sector.append((f"Sector: {sector}", str(count)))

    filas = [
        ("Total Convocatorias", str(total)),
        ("Presupuesto Total (€)", f"{presupuesto:,.2f}"),
        *por_ambito,
        *por_sector,
    ]
    return pd.DataFrame(filas, columns=["Métrica", "Valor"])


def _obtener_columnas_detalle(
    df: pd.DataFrame,
) -> list:
    """Devuelve las columnas disponibles para la tabla detallada."""
    candidatas = [
        "Tipo_Subvencion",
        "Cuantia",
        "Fecha_Vigencia",
        "Entidad_Convocante",
        "Ambito_Territorial",
        "Actividad_Relacionada",
    ]
    return [c for c in candidatas if c in df.columns]


def _acortar_cabeceras(columnas: list) -> list:
    """Acorta los nombres de cabecera para el PDF."""
    mapa = {
        "Tipo_Subvencion": "Convocatoria",
        "Cuantia": "Presupuesto (€)",
        "Fecha_Vigencia": "Vigencia",
        "Entidad_Convocante": "Entidad",
        "Ambito_Territorial": "Ámbito",
        "Actividad_Relacionada": "Sector",
    }
    return [mapa.get(c, c) for c in columnas]


def _truncar(texto: str, max_chars: int) -> str:
    """Trunca un texto largo para que quepa en la celda PDF."""
    if len(texto) <= max_chars:
        return texto
    return texto[: max_chars - 3] + "..."
