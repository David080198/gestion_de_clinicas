"""Modelo Doctor: perfil profesional del medico.

Vinculado 1:1 con un User de rol MEDICO. Contiene los datos profesionales
(licencia, especialidad, biografia) y la tarifa de consulta. Los horarios
de atencion se modelan aparte en DoctorSchedule.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import ForeignKey, Numeric, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.exceptions import ValidationError
from .base import BaseModel


class Doctor(BaseModel):
    """Perfil profesional del medico.

    Attributes:
        user_id: FK al User con rol MEDICO (relacion 1:1).
        license_number: Numero de licencia/cedula profesional (unico).
        specialty: Especialidad medica (Cardiologia, Medicina General, ...).
        bio: Biografia o resumen curricular opcional.
        consultation_fee: Tarifa de la consulta en la moneda de la clinica.
        is_available: Indica si el medico recibe nuevas citas.
    """

    __tablename__ = "doctors"

    # --- Multi-tenancy ---
    clinic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # --- Llave foranea al usuario (1:1) ---
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # --- Datos profesionales ---
    # La licencia es unica DENTRO de cada clinica.
    license_number: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    specialty: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consultation_fee: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, default=Decimal("0.00")
    )
    is_available: Mapped[bool] = mapped_column(default=True, nullable=False)

    # --- Relaciones ---
    clinic: Mapped[Optional["Clinic"]] = relationship("Clinic", back_populates="doctors")
    user: Mapped["User"] = relationship("User", back_populates="doctor_profile")
    schedules: Mapped[list["DoctorSchedule"]] = relationship(
        "DoctorSchedule",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
    medical_records: Mapped[list["MedicalRecord"]] = relationship(
        "MedicalRecord",
        back_populates="doctor",
    )
    prescriptions: Mapped[list["Prescription"]] = relationship(
        "Prescription",
        back_populates="doctor",
    )

    # ============================================================
    # Propiedades derivadas
    # ============================================================

    @property
    def full_name(self) -> str:
        """Nombre completo tomado del usuario vinculado."""
        return self.user.full_name if self.user else ""

    def __repr__(self) -> str:
        return (
            f"<Doctor id={self.id} license={self.license_number!r} "
            f"specialty={self.specialty!r}>"
        )

    # ============================================================
    # Serializacion
    # ============================================================

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = super().to_dict(exclude=exclude)
        data["full_name"] = self.full_name
        if self.consultation_fee is not None:
            data["consultation_fee"] = float(self.consultation_fee)
        return data

    def to_public_dict(self) -> dict[str, Any]:
        """Vista publica del medico (para pacientes al agendar)."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "specialty": self.specialty,
            "consultation_fee": float(self.consultation_fee or 0),
            "is_available": self.is_available,
        }


# ============================================================
# Validaciones a nivel de modelo
# ============================================================

@event.listens_for(Doctor, "before_insert")
@event.listens_for(Doctor, "before_update")
def _validate_doctor(mapper, connection, target: Doctor) -> None:
    """Valida que la cedula y especialidad no esten vacias y la tarifa >= 0."""
    if not target.license_number or not target.license_number.strip():
        raise ValidationError("El numero de licencia es obligatorio.")
    if not target.specialty or not target.specialty.strip():
        raise ValidationError("La especialidad es obligatoria.")
    if target.consultation_fee is not None and target.consultation_fee < 0:
        raise ValidationError("La tarifa de consulta no puede ser negativa.")
