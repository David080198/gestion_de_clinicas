"""Verificacion integral de los modelos de la Fase 1.

Ejecuta la aplicacion con SQLite en memoria, crea todas las tablas y
prueba los flujos criticos:
    - Creacion de usuarios con roles (RBAC) y hashing de contrasena.
    - Perfiles de paciente y medico.
    - Agenda con control de colisiones.
    - Maquina de estados de citas.
    - Expediente clinico inmutable.
    - Receta electronica.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta, timezone

# Configurar entorno de testing antes de importar la app
os.environ["FLASK_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"
os.environ["TEST_DATABASE_URL"] = "sqlite:///:memory:"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import (
    Appointment, AppointmentStatus, BloodType, Doctor, DoctorSchedule,
    Gender, MedicalRecord, Patient, Prescription, User, UserRole, Weekday,
)
from app.exceptions import (
    AppointmentCollisionError, AppointmentStateError, MedicalRecordImmutableError,
    ValidationError,
)


def main() -> None:
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        print("[OK] Tablas creadas en SQLite en memoria.")

        # ---------- 1. Usuarios con roles ----------
        admin = User(email="admin@clinic.com", first_name="Ana", last_name="Admin", role=UserRole.ADMIN)
        admin.set_password("Secret123")
        admin.save()

        medico_user = User(email="dr.house@clinic.com", first_name="Gregory", last_name="House", role=UserRole.MEDICO)
        medico_user.set_password("Secret123")
        medico_user.save()

        recep_user = User(email="recepcion@clinic.com", first_name="Maria", last_name="Recepcion", role=UserRole.RECEPCIONISTA)
        recep_user.set_password("Secret123")
        recep_user.save()

        pac_user = User(email="juan@paciente.com", first_name="Juan", last_name="Perez", role=UserRole.PACIENTE)
        pac_user.set_password("Secret123")
        pac_user.save()

        assert admin.is_admin and medico_user.is_medico and recep_user.is_recepcionista and pac_user.is_paciente
        assert medico_user.check_password("Secret123")
        assert not medico_user.check_password("wrong")
        assert admin.has_role("admin", "medico")
        print("[OK] RBAC: 4 usuarios creados con roles y hashing verificado.")

        # ---------- 2. Perfiles paciente / medico ----------
        patient = Patient(
            user_id=pac_user.id,
            document_number="ABC12345",
            birth_date=date(1990, 5, 15),
            gender=Gender.MASCULINO,
            blood_type=BloodType.O_POS,
            allergies="Penicilina",
        )
        patient.save()

        doctor = Doctor(
            user_id=medico_user.id,
            license_number="MED-001",
            specialty="Medicina Interna",
            consultation_fee=800.00,
        )
        doctor.save()
        print(f"[OK] Perfiles: {patient.full_name} (edad {patient.age}) / Dr. {doctor.full_name} - {doctor.specialty}")

        # ---------- 3. Horario del medico ----------
        schedule = DoctorSchedule(
            doctor_id=doctor.id,
            weekday=Weekday.LUNES,
            start_time=time(9, 0),
            end_time=time(18, 0),
            slot_minutes=30,
        )
        schedule.save()
        assert schedule.contains(time(9, 30), time(10, 0))
        print("[OK] Horario del medico configurado (Lunes 09:00-18:00, slots 30min).")

        # ---------- 4. Cita sin colision ----------
        start = datetime(2026, 6, 22, 9, 0, tzinfo=timezone.utc)  # Lunes
        end = start + timedelta(minutes=30)
        apt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            receptionist_id=recep_user.id,
            start_time=start,
            end_time=end,
            status=AppointmentStatus.PENDIENTE,
            reason="Dolor de cabeza persistente",
        )
        apt.save()
        print(f"[OK] Cita {apt.id} creada: {apt.start_time} estado={apt.status.value}")

        # ---------- 5. Colision detectada ----------
        try:
            apt2 = Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                start_time=start + timedelta(minutes=10),
                end_time=start + timedelta(minutes=40),
                status=AppointmentStatus.PENDIENTE,
            )
            apt2.save()
            print("[FAIL] No se detecto la colision esperada.")
            return
        except AppointmentCollisionError:
            db.session.rollback()
            print("[OK] Colision detectada correctamente (no se permiten 2 citas solapadas).")

        # ---------- 6. Maquina de estados ----------
        apt.transition_to(AppointmentStatus.CONFIRMADA)
        apt.transition_to(AppointmentStatus.EN_CONSULTA)
        db.session.commit()
        print(f"[OK] Transiciones: PENDIENTE -> CONFIRMADA -> EN_CONSULTA")

        try:
            apt.transition_to(AppointmentStatus.PENDIENTE)  # invalida
            print("[FAIL] Transicion invalida permitida.")
            return
        except AppointmentStateError:
            print("[OK] Transicion invalida (EN_CONSULTA -> PENDIENTE) rechazada.")

        # ---------- 7. Expediente clinico ----------
        record = MedicalRecord(
            appointment_id=apt.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            reason="Cefalea tensional",
            symptoms="Dolor bilateral, fotofobia",
            blood_pressure="120/80",
            temperature=36.5,
            heart_rate=72,
            weight=75.0,
            height=170.0,
            diagnosis="Cefalea tensional episodica",
            treatment="Paracetamol 500mg cada 8h, hidratacion, reposo",
        )
        record.save()
        print(f"[OK] Expediente {record.id} creado (inmutable tras guardado).")

        # inmutabilidad
        try:
            record.diagnosis = "Otro diagnostico"
            db.session.commit()
            print("[FAIL] Expediente modificado (deberia ser inmutable).")
            return
        except MedicalRecordImmutableError:
            db.session.rollback()
            print("[OK] Expediente inmutable: modificacion posterior rechazada.")

        # ---------- 8. Receta electronica ----------
        rx = Prescription(
            medical_record_id=record.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            medications=[
                {"name": "Paracetamol", "dose": "500mg", "frequency": "c/8h", "duration": "5 dias", "instructions": "Via oral"},
                {"name": "Ibuprofeno", "dose": "400mg", "frequency": "c/12h", "duration": "3 dias", "instructions": "Con alimentos"},
            ],
            notes="Suspender si aparece rash cutaneo.",
        )
        rx.save()
        print(f"[OK] Receta {rx.code} emitida con {rx.item_count} medicamentos.")
        pdf_data = rx.to_pdf_dict()
        assert pdf_data["doctor_name"] == "Gregory House"
        assert pdf_data["patient_name"] == "Juan Perez"
        print(f"[OK] Estructura PDF: doctor={pdf_data['doctor_name']}, paciente={pdf_data['patient_name']}")

        # receta inmutable
        try:
            rx.notes = "otras notas"
            db.session.commit()
            print("[FAIL] Receta modificada (deberia ser inmutable).")
            return
        except MedicalRecordImmutableError:
            db.session.rollback()
            print("[OK] Receta inmutable: modificacion rechazada.")

        # ---------- 9. Validacion email ----------
        try:
            bad = User(email="no-es-email", first_name="X", last_name="Y", role=UserRole.PACIENTE)
            bad.set_password("Secret123")
            bad.save()
            print("[FAIL] Email invalido aceptado.")
            return
        except ValidationError:
            print("[OK] Validacion de email rechaza formatos invalidos.")

        print("\n========================================")
        print("FASE 1: VERIFICACION COMPLETADA (9/9)")
        print("========================================")


if __name__ == "__main__":
    main()
