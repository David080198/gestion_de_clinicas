"""Modelo MedicalRecord: expediente clinico de una consulta.

Reglas de negocio:
    - El expediente es INMUTABLE una vez creado (auditoria medica).
    - Solo se permite crearlo a partir de una cita en estado EN_CONSULTA
      o COMPLETADA.
    - Pertenece a la relacion 1:1 con la Appointment, pero tambien se
      relaciona con Patient y Doctor para consultas transversales.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.exceptions import (
    MedicalRecordImmutableError,
    RecordNotFoundError,
    ValidationError,
)
from app.extensions import db
from .base import BaseModel
from .enums import AppointmentStatus


class MedicalRecord(BaseModel):
    """Registro de una consulta medica (expediente clinico).

    Attributes:
        appointment_id: FK unico a la cita que origina la consulta (1:1).
        patient_id: FK al paciente (denormalizado para busquedas rapidas).
        doctor_id: FK al medico que atendio (denormalizado).
        reason: Motivo de la visita.
        symptoms: Sintomas reportados por el paciente.
        blood_pressure: Presion arterial en formato "120/80".
        temperature: Temperatura corporal en Celsius.
        heart_rate: Ritmo cardiaco en bpm.
        weight: Peso en kilogramos.
        height: Talla en centimetros.
        diagnosis: Diagnostico / notas de evolucion.
        treatment: Tratamiento sugerido.
        notes: Notas adicionales del medico.
    """

    __tablename__ = "medical_records"
    __table_args__ = (
        Index("ix_medical_records_patient", "patient_id"),
        Index("ix_medical_records_doctor", "doctor_id"),
        Index("ix_medical_records_clinic", "clinic_id"),
    )

    # --- Multi-tenancy ---
    clinic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # --- Llaves foraneas ---
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )

    # --- Motivo y sintomas ---
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    symptoms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Signos vitales ---
    blood_pressure: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heart_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    height: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- Diagnostico y tratamiento ---
    diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Relaciones ---
    appointment: Mapped["Appointment"] = relationship(
        "Appointment", back_populates="medical_record"
    )
    patient: Mapped["Patient"] = relationship("Patient", back_populates="medical_records")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="medical_records")
    prescriptions: Mapped[list["Prescription"]] = relationship(
        "Prescription",
        back_populates="medical_record",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<MedicalRecord id={self.id} patient={self.patient_id} "
            f"doctor={self.doctor_id} appointment={self.appointment_id}>"
        )

    # ============================================================
    # Inmutabilidad (auditoria medica)
    # ============================================================

    @property
    def is_persisted(self) -> bool:
        """Indica si el expediente ya fue guardado en la base de datos."""
        state = db.inspect(self)
        return state.persistent

    def assert_editable(self) -> None:
        """Verifica que el expediente pueda modificarse.

        Raises:
            MedicalRecordImmutableError: Si el expediente ya fue persistido.
        """
        if self.is_persisted:
            raise MedicalRecordImmutableError(
                payload={"medical_record_id": self.id}
            )

    # ============================================================
    # Consultas
    # ============================================================

    @classmethod
    def get_by_appointment(cls, appointment_id: int) -> "MedicalRecord":
        """Recupera el expediente asociado a una cita.

        Raises:
            RecordNotFoundError: Si la cita no tiene expediente.
        """
        record: Optional[MedicalRecord] = (
            db.session.query(cls)
            .filter_by(appointment_id=appointment_id)
            .first()
        )
        if record is None:
            raise RecordNotFoundError(
                f"La cita {appointment_id} no tiene expediente clinico."
            )
        return record

    # ============================================================
    # Serializacion
    # ============================================================

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = super().to_dict(exclude=exclude)
        data["created_at"] = (
            self.created_at.isoformat() if self.created_at else None
        )
        return data


# ============================================================
# Validaciones a nivel de modelo
# ============================================================

@event.listens_for(MedicalRecord, "before_insert")
def _validate_new_record(mapper, connection, target: MedicalRecord) -> None:
    """Valida que el expediente se cree desde una cita valida.

    Reglas:
        - La cita asociada debe estar EN_CONSULTA o COMPLETADA.
        - No debe existir ya un expediente para esa cita (1:1).
        - Signos vitales en rangos plausibles (saneamiento).
    """
    from .appointment import Appointment  # import local para evitar ciclo

    appointment: Optional[Appointment] = db.session.get(Appointment, target.appointment_id)
    if appointment is None:
        raise ValidationError(
            f"La cita {target.appointment_id} no existe."
        )
    if appointment.status not in {
        AppointmentStatus.EN_CONSULTA,
        AppointmentStatus.COMPLETADA,
    }:
        raise ValidationError(
            "Solo se puede crear un expediente para citas en consulta "
            "o completadas."
        )
    # Unicidad 1:1 (la columna unique=True ya lo garantiza a nivel BD,
    # pero damos un error mas amigable antes del commit).
    existing: Optional[MedicalRecord] = (
        db.session.query(MedicalRecord)
        .filter_by(appointment_id=target.appointment_id)
        .first()
    )
    if existing is not None:
        raise ValidationError(
            "Ya existe un expediente clinico para esta cita."
        )

    # --- Saneamiento de signos vitales ---
    if target.temperature is not None and not (30.0 <= target.temperature <= 45.0):
        raise ValidationError("La temperatura debe estar entre 30 y 45 C.")
    if target.heart_rate is not None and not (20 <= target.heart_rate <= 250):
        raise ValidationError("El ritmo cardiaco debe estar entre 20 y 250 bpm.")
    if target.weight is not None and not (0.1 <= target.weight <= 500):
        raise ValidationError("El peso debe estar entre 0.1 y 500 kg.")
    if target.height is not None and not (20 <= target.height <= 250):
        raise ValidationError("La talla debe estar entre 20 y 250 cm.")


@event.listens_for(MedicalRecord, "before_update")
def _prevent_record_modification(mapper, connection, target: MedicalRecord) -> None:
    """Bloquea cualquier modificacion posterior al primer guardado."""
    raise MedicalRecordImmutableError(
        message="Los expedientes clinicos no pueden modificarse despues de su creacion.",
        payload={"medical_record_id": target.id},
    )
