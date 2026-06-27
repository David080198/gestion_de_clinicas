"""Servicio del expediente clinico y recetas electronicas.

Reglas de negocio:
    - Solo el medico asignado a la cita (o un admin) puede crear el
      expediente de esa cita.
    - El expediente es inmutable tras su creacion (auditoria medica).
    - Las recetas se emiten vinculadas a un expediente existente.
    - El paciente puede consultar su historial y descargar sus recetas en PDF.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.exceptions import (
    AuthorizationError,
    MedicalRecordImmutableError,
    RecordNotFoundError,
    ValidationError,
)
from app.extensions import db
from app.models import (
    Appointment,
    AppointmentStatus,
    MedicalRecord,
    Patient,
    Prescription,
    User,
    UserRole,
)
from app.services.pdf_service import PrescriptionPDFBuilder


class MedicalRecordService:
    """Operaciones sobre el expediente clinico."""

    # ============================================================
    # Creacion
    # ============================================================

    @staticmethod
    def create_record(
        appointment_id: int, payload: dict[str, Any], acting_user: User
    ) -> MedicalRecord:
        """Crea el expediente de una cita en estado EN_CONSULTA/COMPLETADA.

        Raises:
            AuthorizationError: Si el usuario no es el medico de la cita.
            ValidationError: Si la cita no esta en un estado valido.
        """
        appointment: Appointment | None = db.session.get(Appointment, appointment_id)
        if appointment is None:
            raise RecordNotFoundError(f"Cita {appointment_id} no encontrada.")

        # --- Permisos ---
        if acting_user.role == UserRole.MEDICO:
            if (
                not acting_user.doctor_profile
                or acting_user.doctor_profile.id != appointment.doctor_id
            ):
                raise AuthorizationError(
                    "Solo el medico asignado a la cita puede crear el expediente."
                )
        elif not acting_user.is_admin:
            raise AuthorizationError(
                "Solo medicos o administradores pueden crear expedientes."
            )

        # --- Estado de la cita ---
        if appointment.status not in {
            AppointmentStatus.EN_CONSULTA,
            AppointmentStatus.COMPLETADA,
        }:
            raise ValidationError(
                "La cita debe estar EN_CONSULTA o COMPLETADA para crear el expediente."
            )

        # --- Unicidad 1:1 ---
        existing: MedicalRecord | None = db.session.scalar(
            select(MedicalRecord).where(
                MedicalRecord.appointment_id == appointment_id
            )
        )
        if existing is not None:
            raise ValidationError("Ya existe un expediente para esta cita.")

        record = MedicalRecord(
            appointment_id=appointment_id,
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            reason=payload.get("reason"),
            symptoms=payload.get("symptoms"),
            blood_pressure=payload.get("blood_pressure"),
            temperature=payload.get("temperature"),
            heart_rate=payload.get("heart_rate"),
            weight=payload.get("weight"),
            height=payload.get("height"),
            diagnosis=payload.get("diagnosis"),
            treatment=payload.get("treatment"),
            notes=payload.get("notes"),
        )
        record.save()
        return record

    # ============================================================
    # Consulta
    # ============================================================

    @staticmethod
    def get_record(record_id: int, acting_user: User) -> MedicalRecord:
        """Recupera un expediente respetando el scope por rol."""
        record: MedicalRecord | None = db.session.get(MedicalRecord, record_id)
        if record is None:
            raise RecordNotFoundError(f"Expediente {record_id} no encontrado.")
        MedicalRecordService._assert_can_view(record, acting_user)
        return record

    @staticmethod
    def get_record_by_appointment(
        appointment_id: int, acting_user: User
    ) -> MedicalRecord:
        """Recupera el expediente asociado a una cita."""
        record: MedicalRecord | None = db.session.scalar(
            select(MedicalRecord).where(
                MedicalRecord.appointment_id == appointment_id
            )
        )
        if record is None:
            raise RecordNotFoundError(
                f"La cita {appointment_id} no tiene expediente clinico."
            )
        MedicalRecordService._assert_can_view(record, acting_user)
        return record

    @staticmethod
    def list_patient_history(
        patient_id: int, acting_user: User
    ) -> list[MedicalRecord]:
        """Historial cronologico de un paciente (inmutable, solo lectura)."""
        # Permisos: paciente ve el suyo; medico/admin ven cualquiera;
        # recepcionista no tiene acceso clinico.
        if acting_user.role == UserRole.RECEPCIONISTA:
            raise AuthorizationError(
                "Los recepcionistas no pueden consultar expedientes clinicos."
            )
        if acting_user.role == UserRole.PACIENTE:
            if (
                not acting_user.patient_profile
                or acting_user.patient_profile.id != patient_id
            ):
                raise AuthorizationError("Solo puedes consultar tu propio historial.")

        stmt = (
            select(MedicalRecord)
            .where(MedicalRecord.patient_id == patient_id)
            .order_by(MedicalRecord.created_at.desc())
        )
        return list(db.session.scalars(stmt))

    @staticmethod
    def _assert_can_view(record: MedicalRecord, user: User) -> None:
        """Verifica permisos de lectura del expediente."""
        if user.is_admin:
            return
        if user.role == UserRole.MEDICO:
            # Los medicos pueden ver todos los expedientes (continuidad del cuidado)
            return
        if user.role == UserRole.PACIENTE:
            if (
                not user.patient_profile
                or user.patient_profile.id != record.patient_id
            ):
                raise AuthorizationError("Solo puedes ver tu propio expediente.")
            return
        raise AuthorizationError("No tienes permiso para ver expedientes clinicos.")


# ============================================================
# Recetas
# ============================================================

class PrescriptionService:
    """Operaciones sobre recetas electronicas."""

    @staticmethod
    def create_prescription(
        medical_record_id: int, payload: dict[str, Any], acting_user: User
    ) -> Prescription:
        """Emite una receta asociada a un expediente existente.

        Raises:
            AuthorizationError: Si el usuario no es el medico del expediente.
            RecordNotFoundError: Si el expediente no existe.
        """
        record: MedicalRecord | None = db.session.get(MedicalRecord, medical_record_id)
        if record is None:
            raise RecordNotFoundError(f"Expediente {medical_record_id} no encontrado.")

        if acting_user.role == UserRole.MEDICO:
            if acting_user.doctor_profile is None or acting_user.doctor_profile.id != record.doctor_id:
                raise AuthorizationError(
                    "Solo el medico que atendio puede emitir la receta."
                )
        elif not acting_user.is_admin:
            raise AuthorizationError(
                "Solo medicos o administradores pueden emitir recetas."
            )

        rx = Prescription(
            medical_record_id=medical_record_id,
            patient_id=record.patient_id,
            doctor_id=record.doctor_id,
            medications=payload["medications"],
            notes=payload.get("notes"),
        )
        rx.save()
        return rx

    @staticmethod
    def get_prescription(code: str, acting_user: User) -> Prescription:
        """Recupera una receta por su codigo unico con scope por rol."""
        rx: Prescription = Prescription.get_by_code(code)
        PrescriptionService._assert_can_view(rx, acting_user)
        return rx

    @staticmethod
    def list_patient_prescriptions(
        patient_id: int, acting_user: User
    ) -> list[Prescription]:
        """Lista las recetas de un paciente (descarga del paciente)."""
        if acting_user.role == UserRole.PACIENTE:
            if (
                not acting_user.patient_profile
                or acting_user.patient_profile.id != patient_id
            ):
                raise AuthorizationError("Solo puedes ver tus propias recetas.")
        elif acting_user.role == UserRole.RECEPCIONISTA:
            raise AuthorizationError("Los recepcionistas no pueden consultar recetas.")

        stmt = (
            select(Prescription)
            .where(Prescription.patient_id == patient_id)
            .order_by(Prescription.created_at.desc())
        )
        return list(db.session.scalars(stmt))

    @staticmethod
    def generate_pdf(code: str, acting_user: User) -> bytes:
        """Genera el PDF imprimible de una receta.

        Returns:
            Contenido del PDF en bytes.
        """
        rx: Prescription = Prescription.get_by_code(code)
        PrescriptionService._assert_can_view(rx, acting_user)
        return PrescriptionPDFBuilder.build(rx)

    @staticmethod
    def _assert_can_view(rx: Prescription, user: User) -> None:
        if user.is_admin:
            return
        if user.role == UserRole.MEDICO:
            # medicos pueden ver todas las recetas (continuidad del cuidado)
            return
        if user.role == UserRole.PACIENTE:
            if (
                not user.patient_profile
                or user.patient_profile.id != rx.patient_id
            ):
                raise AuthorizationError("Solo puedes ver tus propias recetas.")
            return
        raise AuthorizationError("No tienes permiso para ver recetas.")
