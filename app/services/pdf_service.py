"""Generador de PDFs de recetas medicas usando reportlab.

Produce un PDF profesional con membrete, datos del medico/paciente,
tabla de medicamentos y notas. El resultado se entrega como bytes
para que el endpoint lo sirva como descarga directa.
"""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models import Prescription


class PrescriptionPDFBuilder:
    """Construye el PDF imprimible de una receta medica."""

    @staticmethod
    def build(rx: Prescription) -> bytes:
        """Genera el PDF de la receta y retorna los bytes."""
        data: dict = rx.to_pdf_dict()
        buffer: BytesIO = BytesIO()

        doc: SimpleDocTemplate = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title=f"Receta {data['code']}",
        )

        styles = getSampleStyleSheet()
        title_style: ParagraphStyle = ParagraphStyle(
            "RxTitle",
            parent=styles["Title"],
            fontSize=20,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=6,
        )
        subtitle_style: ParagraphStyle = ParagraphStyle(
            "RxSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#475569"),
            spaceAfter=4,
        )
        section_style: ParagraphStyle = ParagraphStyle(
            "RxSection",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#1e3a8a"),
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style: ParagraphStyle = ParagraphStyle(
            "RxBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
        )

        story = []
        # --- Membrete ---
        story.append(Paragraph("Receta Medica Electronica", title_style))
        story.append(Paragraph(f"Codigo: <b>{data['code']}</b>", subtitle_style))
        story.append(Paragraph(f"Emitida: {data['issued_at']}", subtitle_style))
        story.append(Spacer(1, 0.6 * cm))

        # --- Medico ---
        story.append(Paragraph("Medico", section_style))
        story.append(Paragraph(f"Nombre: <b>{data['doctor_name']}</b>", body_style))
        story.append(Paragraph(f"Especialidad: {data['doctor_specialty']}", body_style))
        story.append(Paragraph(f"Licencia: {data['doctor_license']}", body_style))
        story.append(Spacer(1, 0.4 * cm))

        # --- Paciente ---
        story.append(Paragraph("Paciente", section_style))
        story.append(Paragraph(f"Nombre: <b>{data['patient_name']}</b>", body_style))
        story.append(Paragraph(f"Documento: {data['patient_document']}", body_style))
        age = data.get("patient_age")
        if age is not None:
            story.append(Paragraph(f"Edad: {age} anos", body_style))
        story.append(Spacer(1, 0.4 * cm))

        # --- Tabla de medicamentos ---
        story.append(Paragraph("Medicamentos", section_style))
        header = ["#", "Medicamento", "Dosis", "Frecuencia", "Duracion", "Indicaciones"]
        rows = [header]
        for idx, med in enumerate(data["medications"], start=1):
            rows.append([
                str(idx),
                med.get("name", ""),
                med.get("dose", "") or "-",
                med.get("frequency", "") or "-",
                med.get("duration", "") or "-",
                med.get("instructions", "") or "-",
            ])
        table: Table = Table(
            rows,
            colWidths=[0.8 * cm, 4 * cm, 2.4 * cm, 2.6 * cm, 2.4 * cm, 5 * cm],
        )
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(table)
        story.append(Spacer(1, 0.6 * cm))

        # --- Indicaciones generales ---
        if data.get("notes"):
            story.append(Paragraph("Indicaciones generales", section_style))
            story.append(Paragraph(data["notes"], body_style))

        # --- Firma ---
        story.append(Spacer(1, 1.5 * cm))
        story.append(Paragraph("_" * 40, body_style))
        story.append(Paragraph(f"Firma: {data['doctor_name']}", body_style))

        doc.build(story)
        pdf_bytes: bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
