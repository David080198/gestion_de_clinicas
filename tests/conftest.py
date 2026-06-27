"""Configuracion compartida para los tests de pytest."""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///:memory:")

from app import create_app
from app.extensions import db
from app.models import (
    AppointmentStatus,
    Doctor,
    DoctorSchedule,
    Gender,
    Patient,
    User,
    UserRole,
    Weekday,
)


@pytest.fixture
def app():
    """Crea y configura una aplicacion Flask para testing."""
    app = create_app("testing")
    app.config["JWT_COOKIE_SECURE"] = False
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    app.config["JWT_TOKEN_LOCATION"] = ["cookies", "headers"]

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Cliente de test de Flask."""
    return app.test_client()


@pytest.fixture
def admin_user(app):
    """Crea un usuario admin de prueba."""
    with app.app_context():
        user = User(
            email="admin@test.com",
            first_name="Ana",
            last_name="Admin",
            role=UserRole.ADMIN,
        )
        user.set_password("Admin123!")
        user.save()
        yield user


@pytest.fixture
def doctor_user(app):
    """Crea un usuario medico de prueba con perfil de doctor."""
    with app.app_context():
        user = User(
            email="doctor@test.com",
            first_name="Gregory",
            last_name="House",
            role=UserRole.MEDICO,
        )
        user.set_password("Medico123!")
        user.save()
        doctor = Doctor(
            user_id=user.id,
            license_number="MED-TEST-001",
            specialty="Medicina Interna",
            consultation_fee=800.00,
        )
        doctor.save()
        schedule = DoctorSchedule(
            doctor_id=doctor.id,
            weekday=Weekday.LUNES,
            start_time=time(9, 0),
            end_time=time(18, 0),
            slot_minutes=30,
        )
        schedule.save()
        yield user


@pytest.fixture
def patient_user(app):
    """Crea un usuario paciente de prueba con perfil de paciente."""
    with app.app_context():
        user = User(
            email="patient@test.com",
            first_name="Juan",
            last_name="Perez",
            role=UserRole.PACIENTE,
        )
        user.set_password("Secret123")
        user.save()
        patient = Patient(
            user_id=user.id,
            document_number="DOC-TEST-001",
            birth_date=date(1990, 5, 15),
            gender=Gender.MASCULINO,
        )
        patient.save()
        yield user


@pytest.fixture
def auth_client(client, app):
    """Helper para loguear un usuario y retornar (client, headers)."""

    def _login(email: str, password: str):
        resp = client.post("/api/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200
        return client

    return _login
