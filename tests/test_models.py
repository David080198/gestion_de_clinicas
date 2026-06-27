"""Tests de modelos de datos (Fase 1)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.exceptions import (
    AppointmentCollisionError,
    AppointmentStateError,
    MedicalRecordImmutableError,
    ValidationError,
)
from app.extensions import db
from app.models import (
    Appointment,
    AppointmentStatus,
    BloodType,
    Doctor,
    DoctorSchedule,
    Gender,
    MedicalRecord,
    Patient,
    Prescription,
    User,
    UserRole,
    Weekday,
)


def test_user_roles_and_password_hashing(app):
    with app.app_context():
        admin = User(
            email="admin@clinic.com",
            first_name="Ana",
            last_name="Admin",
            role=UserRole.ADMIN,
        )
        admin.set_password("Secret123")
        admin.save()

        assert admin.is_admin
        assert admin.check_password("Secret123")
        assert not admin.check_password("wrong")
        assert admin.has_role("admin", "medico")


def test_patient_profile(app):
    with app.app_context():
        user = User(
            email="patient@clinic.com",
            first_name="Juan",
            last_name="Perez",
            role=UserRole.PACIENTE,
        )
        user.set_password("Secret123")
        user.save()

        patient = Patient(
            user_id=user.id,
            document_number="ABC123",
            birth_date=date(1990, 5, 15),
            gender=Gender.MASCULINO,
            blood_type=BloodType.O_POS,
        )
        patient.save()

        assert patient.full_name == "Juan Perez"
        assert patient.age >= 34


def test_appointment_collision(app, doctor_user, patient_user):
    with app.app_context():
        doctor = Doctor.query.filter_by(user_id=doctor_user.id).first()
        patient = Patient.query.filter_by(user_id=patient_user.id).first()
        receptionist = User(
            email="recep@clinic.com",
            first_name="Maria",
            last_name="Recep",
            role=UserRole.RECEPCIONISTA,
        )
        receptionist.set_password("Secret123")
        receptionist.save()

        start = datetime(2026, 6, 22, 9, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=30)

        apt1 = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            receptionist_id=receptionist.id,
            start_time=start,
            end_time=end,
            status=AppointmentStatus.PENDIENTE,
        )
        apt1.save()

        with pytest.raises(AppointmentCollisionError):
            apt2 = Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                receptionist_id=receptionist.id,
                start_time=start + timedelta(minutes=10),
                end_time=end + timedelta(minutes=10),
                status=AppointmentStatus.PENDIENTE,
            )
            apt2.save()


def test_appointment_state_machine(app, doctor_user, patient_user):
    with app.app_context():
        doctor = Doctor.query.filter_by(user_id=doctor_user.id).first()
        patient = Patient.query.filter_by(user_id=patient_user.id).first()

        start = datetime(2026, 6, 22, 10, 0, tzinfo=timezone.utc)
        apt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status=AppointmentStatus.PENDIENTE,
        )
        apt.save()

        apt.transition_to(AppointmentStatus.CONFIRMADA)
        apt.transition_to(AppointmentStatus.EN_CONSULTA)
        db.session.commit()

        with pytest.raises(AppointmentStateError):
            apt.transition_to(AppointmentStatus.PENDIENTE)


def test_medical_record_immutability(app, doctor_user, patient_user):
    with app.app_context():
        doctor = Doctor.query.filter_by(user_id=doctor_user.id).first()
        patient = Patient.query.filter_by(user_id=patient_user.id).first()

        start = datetime(2026, 6, 22, 11, 0, tzinfo=timezone.utc)
        apt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status=AppointmentStatus.COMPLETADA,
        )
        apt.save()

        record = MedicalRecord(
            appointment_id=apt.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            diagnosis="Cefalea",
        )
        record.save()

        with pytest.raises(MedicalRecordImmutableError):
            record.diagnosis = "Otro diagnostico"
            db.session.commit()


def test_email_validation(app):
    with app.app_context():
        with pytest.raises(ValidationError):
            user = User(
                email="no-es-email",
                first_name="X",
                last_name="Y",
                role=UserRole.PACIENTE,
            )
            user.set_password("Secret123")
            user.save()
