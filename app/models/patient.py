"""Modelo Patient: perfil clinico y demografico del paciente.

Se vincula 1:1 con un User de rol PACIENTE. Contiene datos demograficos
y clinicos generales (tipo de sangre, contacto de emergencia) que sirven
de contexto para las consultas y el expediente.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import Date, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.exceptions import RecordNotFoundError
from .base import BaseModel
from .enums import BloodType, Gender


class Patient(BaseModel):
    """Perfil de paciente vinculado a una cuenta de usuario.

    Attributes:
        user_id: FK al User con rol PACIENTE.
        document_number: DNI/identificacion oficial unica.
        birth_date: Fecha de nacimiento.
        gender: Sexo biologico.
        blood_type: Tipo de sangre.
        address: Direccion de residencia.
        emergency_contact_name: Nombre del contacto de emergencia.
        emergency_contact_phone: Telefono del contacto de emergencia.
        allergies: Texto libre con alergias conocidas.
    """

    __tablename__ = "patients"
    __table_args__ = (
        Index("ix_patients_clinic", "clinic_id"),
    )

    # --- Multi-tenancy ---
    clinic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # --- Llave foranea al usuario ---
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # --- Identificacion ---
    # El documento es unico DENTRO de cada clinica, no globalmente.
    document_number: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender] = mapped_column(
        Enum(Gender, name="gender"),
        nullable=False,
        default=Gender.NO_ESPECIFICADO,
    )
    blood_type: Mapped[BloodType] = mapped_column(
        Enum(BloodType, name="blood_type"),
        nullable=False,
        default=BloodType.DESCONOCIDO,
    )

    # --- Contacto ---
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True
    )
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )

    # --- Clinico general ---
    allergies: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # --- Relaciones ---
    clinic: Mapped[Optional["Clinic"]] = relationship("Clinic", back_populates="patients")
    user: Mapped["User"] = relationship("User", back_populates="patient_profile")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    medical_records: Mapped[list["MedicalRecord"]] = relationship(
        "MedicalRecord",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    prescriptions: Mapped[list["Prescription"]] = relationship(
        "Prescription",
        back_populates="patient",
        cascade="all, delete-orphan",
    )

    # ============================================================
    # Propiedades derivadas
    # ============================================================

    @property
    def full_name(self) -> str:
        """Nombre completo tomado del usuario vinculado."""
        return self.user.full_name if self.user else ""

    @property
    def age(self) -> Optional[int]:
        """Edad calculada a partir de la fecha de nacimiento."""
        if not self.birth_date:
            return None
        today: date = date.today()
        years: int = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    def __repr__(self) -> str:
        return (
            f"<Patient id={self.id} doc={self.document_number!r} "
            f"name={self.full_name!r}>"
        )

    # ============================================================
    # Serializacion
    # ============================================================

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = super().to_dict(exclude=exclude)
        data["full_name"] = self.full_name
        data["age"] = self.age
        return data

    @classmethod
    def find_by_document(cls, document_number: str) -> "Patient":
        """Busca un paciente por su numero de documento.

        Raises:
            RecordNotFoundError: Si no existe un paciente con ese documento.
        """
        from app.extensions import db

        patient: Optional[Patient] = (
            db.session.query(cls)
            .filter_by(document_number=document_number)
            .first()
        )
        if patient is None:
            raise RecordNotFoundError(
                f"No existe paciente con documento {document_number!r}."
            )
        return patient
