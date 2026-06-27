"""Modelo Prescription: receta medica electronica.

Una receta se emite durante una consulta y pertenece a un MedicalRecord.
Los medicamentos se almacenan como un arreglo JSON para soportar multiples
lineas de prescripcion con dosis, frecuencia y duracion cada una.

Reglas:
    - La receta es inmutable una vez emitida (auditoria).
    - Solo puede crearla el medico que atendio la consulta.
    - Genera un codigo unico para su impresion/trazabilidad en PDF.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import ForeignKey, Index, String, Text, event, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.exceptions import (
    MedicalRecordImmutableError,
    RecordNotFoundError,
    ValidationError,
)
from app.extensions import db
from .base import BaseModel


class Prescription(BaseModel):
    """Receta medica electronica vinculada a un expediente clinico.

    Attributes:
        code: Codigo unico de receta (ej: "RX-2026-0001-AB12") para PDF.
        medical_record_id: FK al expediente que origina la receta.
        patient_id: FK al paciente (denormalizado para descargas del paciente).
        doctor_id: FK al medico emisor (denormalizado).
        medications: Lista de items [{name, dose, frequency, duration, instructions}].
        notes: Indicaciones generales de la receta.
        issued_at: Fecha/hora de emision (alias de created_at para el PDF).
    """

    __tablename__ = "prescriptions"
    __table_args__ = (
        Index("ix_prescriptions_patient", "patient_id"),
        Index("ix_prescriptions_doctor", "doctor_id"),
        Index("ix_prescriptions_code", "code", unique=True),
        Index("ix_prescriptions_clinic", "clinic_id"),
    )

    # --- Multi-tenancy ---
    clinic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # --- Identificacion ---
    code: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True, default=lambda: _generate_code()
    )

    # --- Llaves foraneas ---
    medical_record_id: Mapped[int] = mapped_column(
        ForeignKey("medical_records.id", ondelete="CASCADE"), nullable=False
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )

    # --- Contenido ---
    medications: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Relaciones ---
    medical_record: Mapped["MedicalRecord"] = relationship(
        "MedicalRecord", back_populates="prescriptions"
    )
    patient: Mapped["Patient"] = relationship("Patient", back_populates="prescriptions")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="prescriptions")

    def __repr__(self) -> str:
        return (
            f"<Prescription code={self.code!r} patient={self.patient_id} "
            f"items={len(self.medications)}>"
        )

    # ============================================================
    # Propiedades
    # ============================================================

    @property
    def issued_at(self) -> Any:
        """Fecha de emision (alias de created_at)."""
        return self.created_at

    @property
    def item_count(self) -> int:
        """Numero de medicamentos en la receta."""
        return len(self.medications) if self.medications else 0

    # ============================================================
    # Serializacion
    # ============================================================

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = super().to_dict(exclude=exclude)
        data["item_count"] = self.item_count
        data["issued_at"] = (
            self.issued_at.isoformat() if self.issued_at else None
        )
        return data

    def to_pdf_dict(self) -> dict[str, Any]:
        """Estructura orientada a la generacion del PDF imprimible."""
        doctor_name: str = self.doctor.full_name if self.doctor else ""
        patient_name: str = self.patient.full_name if self.patient else ""
        return {
            "code": self.code,
            "issued_at": self.issued_at.isoformat() if self.issued_at else "",
            "doctor_name": doctor_name,
            "doctor_specialty": self.doctor.specialty if self.doctor else "",
            "doctor_license": self.doctor.license_number if self.doctor else "",
            "patient_name": patient_name,
            "patient_document": self.patient.document_number if self.patient else "",
            "patient_age": self.patient.age if self.patient else None,
            "medications": self.medications or [],
            "notes": self.notes or "",
        }

    # ============================================================
    # Consultas
    # ============================================================

    @classmethod
    def get_by_code(cls, code: str) -> "Prescription":
        """Recupera una receta por su codigo unico.

        Raises:
            RecordNotFoundError: Si no existe receta con ese codigo.
        """
        rx: Optional[Prescription] = (
            db.session.query(cls).filter_by(code=code).first()
        )
        if rx is None:
            raise RecordNotFoundError(f"No existe receta con codigo {code!r}.")
        return rx


# ============================================================
# Utilidades
# ============================================================

def _generate_code() -> str:
    """Genera un codigo unico de receta legible para impresion.

    Formato: RX-<año>-<uuid corto>
    """
    year: int = __import__("datetime").datetime.utcnow().year
    short: str = uuid.uuid4().hex[:8].upper()
    return f"RX-{year}-{short}"


# ============================================================
# Validaciones a nivel de modelo
# ============================================================

@event.listens_for(Prescription, "before_insert")
def _validate_new_prescription(mapper, connection, target: Prescription) -> None:
    """Valida que la receta tenga al menos un medicamento con estructura correcta."""
    if not target.medications or not isinstance(target.medications, list):
        raise ValidationError("La receta debe incluir al menos un medicamento.")
    for idx, item in enumerate(target.medications):
        if not isinstance(item, dict):
            raise ValidationError(
                f"El medicamento #{idx + 1} debe ser un objeto."
            )
        name: Any = item.get("name")
        if not name or not str(name).strip():
            raise ValidationError(
                f"El medicamento #{idx + 1} requiere un nombre."
            )


@event.listens_for(Prescription, "before_update")
def _prevent_prescription_modification(mapper, connection, target: Prescription) -> None:
    """Las recetas son inmutables una vez emitidas (auditoria medica)."""
    raise MedicalRecordImmutableError(
        message="Las recetas medicas no pueden modificarse despues de emitirse.",
        payload={"prescription_id": target.id, "code": target.code},
    )
