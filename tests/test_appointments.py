"""Tests de agendamiento de citas (Fase 2)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.extensions import db
from app.models import Appointment, AppointmentStatus, Doctor, Patient, User, UserRole


def _next_monday():
    today = date.today()
    days_to_monday = (7 - today.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    return today + timedelta(days=days_to_monday)


def test_create_appointment(client, app, doctor_user, patient_user):
    with app.app_context():
        doctor = Doctor.query.filter_by(user_id=doctor_user.id).first()
        patient = Patient.query.filter_by(user_id=patient_user.id).first()
        recep = User(
            email="recep@test.com",
            first_name="Maria",
            last_name="Recep",
            role=UserRole.RECEPCIONISTA,
        )
        recep.set_password("Secret123")
        recep.save()
        doctor_id = doctor.id
        patient_id = patient.id

    client.post(
        "/api/auth/login",
        json={"email": "recep@test.com", "password": "Secret123"},
    )

    next_monday = _next_monday()
    start = datetime.combine(next_monday, time(9, 0), tzinfo=timezone.utc)

    resp = client.post(
        "/api/appointments",
        json={
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=30)).isoformat(),
            "reason": "Dolor de cabeza",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["appointment"]["status"] in ("confirmada", "pendiente")


def test_appointment_collision_returns_409(client, app, doctor_user, patient_user):
    with app.app_context():
        doctor = Doctor.query.filter_by(user_id=doctor_user.id).first()
        patient = Patient.query.filter_by(user_id=patient_user.id).first()
        recep = User(
            email="recep2@test.com",
            first_name="Maria",
            last_name="Recep",
            role=UserRole.RECEPCIONISTA,
        )
        recep.set_password("Secret123")
        recep.save()
        doctor_id = doctor.id
        patient_id = patient.id

    client.post(
        "/api/auth/login",
        json={"email": "recep2@test.com", "password": "Secret123"},
    )

    next_monday = _next_monday()
    start = datetime.combine(next_monday, time(10, 0), tzinfo=timezone.utc)

    resp1 = client.post(
        "/api/appointments",
        json={
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=30)).isoformat(),
            "reason": "Primera cita",
        },
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        "/api/appointments",
        json={
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "start_time": (start + timedelta(minutes=10)).isoformat(),
            "end_time": (start + timedelta(minutes=40)).isoformat(),
            "reason": "Cita solapada",
        },
    )
    assert resp2.status_code == 409


def test_patient_cannot_create_record(client, app, doctor_user, patient_user):
    with app.app_context():
        doctor = Doctor.query.filter_by(user_id=doctor_user.id).first()
        patient = Patient.query.filter_by(user_id=patient_user.id).first()

    client.post(
        "/api/auth/login",
        json={"email": "patient@test.com", "password": "Secret123"},
    )

    resp = client.post("/api/medical/appointments/1/record", json={"reason": "intento"})
    assert resp.status_code == 403
