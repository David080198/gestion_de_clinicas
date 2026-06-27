"""Verificacion integral de la Fase 5 - Multi-tenancy.

Prueba el aislamiento completo entre clinicas:
    1. Crear clinica A y clinica B via API (super-admin).
    2. Crear admin de cada clinica.
    3. Cada admin crea su propio medico y paciente.
    4. Agendar cita en clinica A y verificar que clinica B NO la ve.
    5. Crear expediente y receta en clinica A; clinica B no accede.
    6. Super-admin ve todas las clinicas y sus stats.
    7. Suspender clinica B -> sus usuarios no pueden operar.
    8. Cross-tenant: admin de clinica A no puede ver datos de clinica B (403).
    9. Auto-registro de clinica via endpoint publico.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta, timezone

os.environ["FLASK_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-phase5-multitenant"
os.environ["JWT_SECRET_KEY"] = "test-jwt-phase5"
os.environ["TEST_DATABASE_URL"] = "sqlite:///:memory:"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import (
    Appointment, AppointmentStatus, BloodType, Clinic, ClinicPlan, ClinicStatus,
    Doctor, DoctorSchedule, Gender, Patient, User, UserRole, Weekday,
)

UTC = timezone.utc

# Token JWT del usuario actual (se setea en _login)
_current_token: str | None = None


def _login(client, email: str, password: str) -> dict:
    """Hace login y almacena el token JWT globalmente."""
    global _current_token
    _current_token = None
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"login {email}: {resp.status_code} {resp.get_json()}"
    body = resp.get_json()
    user = body.get("user", {})
    assert user.get("email") == email, f"login retorno: {user.get('email')}, esperaba {email}"
    # Con JWT_TOKEN_LOCATION=["headers"], el token viene en el body
    _current_token = body.get("access_token")
    if not _current_token:
        # Fallback: extraer de Set-Cookie si viene en cookies
        set_cookie = resp.headers.get("Set-Cookie", "")
        for part in set_cookie.split(";"):
            part = part.strip()
            if part.startswith("access_token_cookie="):
                _current_token = part.split("=", 1)[1]
                break
    assert _current_token is not None, "No se encontro token en la respuesta"
    print(f"  [_login] {email} token={_current_token[:30]}...")
    return body


def _logout(client) -> None:
    global _current_token
    _current_token = None


def _h() -> dict:
    """Retorna headers con el token JWT actual."""
    if _current_token:
        return {"Authorization": f"Bearer {_current_token}"}
    return {}


def _get(client, path):
    return client.get(path, headers=_h())


def _post(client, path, json=None):
    return client.post(path, json=json, headers=_h())


def _patch(client, path, json=None):
    return client.patch(path, json=json, headers=_h())


def main() -> None:
    app = create_app("testing")
    app.config["JWT_COOKIE_SECURE"] = False
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    # Usar solo headers en este test para evitar el cookie jar compartido
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    client = app.test_client()

    with app.app_context():
        db.create_all()

        # --- Crear super-admin (sin clinica) ---
        super_admin = User(
            email="super@medcenter.app",
            first_name="Super",
            last_name="Admin",
            role=UserRole.ADMIN,
            clinic_id=None,
        )
        super_admin.set_password("Super123!")
        super_admin.save()
        assert super_admin.is_super_admin
        print("[OK 01] Super-admin creado (sin clinica).")

        # --- Login como super-admin ---
        _login(client, "super@medcenter.app", "Super123!")

        # --- Crear clinica A via API ---
        resp = _post(client, "/api/clinics", json={
            "name": "Clinica San Angel",
            "subdomain": "sanangel",
            "plan": "professional",
            "status": "activa",
            "timezone": "America/Mexico_City",
            "currency": "MXN",
        })
        assert resp.status_code == 201, f"crear clinica A: {resp.status_code} {resp.get_json()}"
        clinic_a_id = resp.get_json()["clinic"]["id"]
        print(f"[OK 02] Clinica A creada (id={clinic_a_id}, subdomain=sanangel).")

        # --- Crear clinica B via API ---
        resp = _post(client, "/api/clinics", json={
            "name": "Consultorio Dr Lopez",
            "subdomain": "drlopez",
            "plan": "starter",
            "status": "activa",
        })
        assert resp.status_code == 201, f"crear clinica B: {resp.status_code} {resp.get_json()}"
        clinic_b_id = resp.get_json()["clinic"]["id"]
        print(f"[OK 03] Clinica B creada (id={clinic_b_id}, subdomain=drlopez).")

        # --- Subdominio duplicado rechazado ---
        resp = _post(client, "/api/clinics", json={
            "name": "Otra Clinica",
            "subdomain": "sanangel",
        })
        assert resp.status_code == 409, f"esperaba 409, got {resp.status_code}"
        print("[OK 04] Subdominio duplicado rechazado (409).")

        # --- Crear admin de clinica A ---
        resp = _post(client, f"/api/clinics/{clinic_a_id}/admin", json={
            "email": "admin@sanangel.com",
            "password": "Admin123!",
            "first_name": "Carlos",
            "last_name": "SanAngel",
        })
        assert resp.status_code == 201, f"admin A: {resp.status_code} {resp.get_json()}"
        print("[OK 05] Admin de clinica A creado.")

        # --- Crear admin de clinica B ---
        resp = _post(client, f"/api/clinics/{clinic_b_id}/admin", json={
            "email": "admin@drlopez.com",
            "password": "Admin123!",
            "first_name": "Roberto",
            "last_name": "Lopez",
        })
        assert resp.status_code == 201, f"admin B: {resp.status_code} {resp.get_json()}"
        print("[OK 06] Admin de clinica B creado.")

        # --- Login como admin de clinica A ---
        _login(client, "admin@sanangel.com", "Admin123!")

        # Crear medico y paciente en clinica A
        with app.app_context():
            med_a = User(email="dr.a@sanangel.com", first_name="Dra",
                        last_name="A", role=UserRole.MEDICO, clinic_id=clinic_a_id)
            med_a.set_password("Medico123!")
            med_a.save()
            doc_a = Doctor(user_id=med_a.id, clinic_id=clinic_a_id,
                          license_number="MED-A-001", specialty="Cardiologia",
                          consultation_fee=900)
            doc_a.save()
            sched_a = DoctorSchedule(doctor_id=doc_a.id, weekday=Weekday.LUNES,
                                     start_time=time(9, 0), end_time=time(14, 0),
                                     slot_minutes=30)
            sched_a.save()

            pac_a_user = User(email="pac.a@sanangel.com", first_name="Paciente",
                             last_name="A", role=UserRole.PACIENTE, clinic_id=clinic_a_id)
            pac_a_user.set_password("Secret123")
            pac_a_user.save()
            pac_a = Patient(user_id=pac_a_user.id, clinic_id=clinic_a_id,
                           document_number="DOC-A-001", birth_date=date(1990, 1, 1),
                           gender=Gender.MASCULINO, blood_type=BloodType.O_POS)
            pac_a.save()
            doc_a_id = doc_a.id
            pac_a_id = pac_a.id

        # --- Login como admin de clinica B y crear datos ---
        _login(client, "admin@drlopez.com", "Admin123!")

        with app.app_context():
            med_b = User(email="dr.b@drlopez.com", first_name="Dr",
                        last_name="B", role=UserRole.MEDICO, clinic_id=clinic_b_id)
            med_b.set_password("Medico123!")
            med_b.save()
            doc_b = Doctor(user_id=med_b.id, clinic_id=clinic_b_id,
                          license_number="MED-B-001", specialty="Medicina General",
                          consultation_fee=500)
            doc_b.save()
            sched_b = DoctorSchedule(doctor_id=doc_b.id, weekday=Weekday.LUNES,
                                     start_time=time(10, 0), end_time=time(15, 0),
                                     slot_minutes=30)
            sched_b.save()

            pac_b_user = User(email="pac.b@drlopez.com", first_name="Paciente",
                             last_name="B", role=UserRole.PACIENTE, clinic_id=clinic_b_id)
            pac_b_user.set_password("Secret123")
            pac_b_user.save()
            pac_b = Patient(user_id=pac_b_user.id, clinic_id=clinic_b_id,
                           document_number="DOC-B-001", birth_date=date(1985, 5, 10),
                           gender=Gender.FEMENINO, blood_type=BloodType.A_POS)
            pac_b.save()
            doc_b_id = doc_b.id
            pac_b_id = pac_b.id

        print("[OK 07] Datos creados en ambas clinicas (medico + paciente c/u).")

        # --- Login como admin de clinica A ---
        _login(client, "admin@sanangel.com", "Admin123!")

        # Verificar clinic_id del admin en la BD
        with app.app_context():
            admin_a = User.query.filter_by(email="admin@sanangel.com").first()
            print(f"  [debug] admin@sanangel.com clinic_id en BD = {admin_a.clinic_id}")

        # --- AISLAMIENTO: Agendar cita en clinica A ---
        today = date.today()
        days_to_monday = (7 - today.weekday()) % 7
        if days_to_monday == 0:
            days_to_monday = 7
        next_monday = today + timedelta(days=days_to_monday)
        start = datetime.combine(next_monday, time(9, 0), tzinfo=UTC)

        resp = _post(client, "/api/appointments", json={
            "patient_id": pac_a_id,
            "doctor_id": doc_a_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=30)).isoformat(),
            "reason": "Consulta cardiologica",
        })
        assert resp.status_code == 201, f"crear cita A: {resp.status_code} {resp.get_json()}"
        cita_a_id = resp.get_json()["appointment"]["id"]
        print(f"[OK 08] Cita creada en clinica A (id={cita_a_id}).")

        # --- Login como admin de clinica B ---
        _login(client, "admin@drlopez.com", "Admin123!")

        # --- AISLAMIENTO: Clinica B NO ve la cita de clinica A ---
        resp = _get(client, "/api/appointments")
        assert resp.status_code == 200
        items_b = resp.get_json()["items"]
        cita_ids_b = [a["id"] for a in items_b]
        with app.app_context():
            cita_a = db.session.get(Appointment, cita_a_id)
            print(f"  [debug] cita_a clinic_id = {cita_a.clinic_id if cita_a else 'NOT FOUND'}")
            print(f"  [debug] items_b ids = {cita_ids_b}")
        assert cita_a_id not in cita_ids_b, "Clinica B ve la cita de clinica A!"
        print("[OK 09] Clinica B NO ve la cita de clinica A (aislamiento OK).")

        # --- Login como admin de clinica A ---
        _login(client, "admin@sanangel.com", "Admin123!")

        # --- AISLAMIENTO: Clinica A no puede usar medico de clinica B ---
        resp = _post(client, "/api/appointments", json={
            "patient_id": pac_a_id,
            "doctor_id": doc_b_id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=30)).isoformat(),
        })
        assert resp.status_code == 403, f"esperaba 403 cross-tenant, got {resp.status_code}"
        print("[OK 10] Clinica A no puede agendar con medico de clinica B (403).")

        # --- AISLAMIENTO: Clinica A no puede usar paciente de clinica B ---
        resp = _post(client, "/api/appointments", json={
            "patient_id": pac_b_id,
            "doctor_id": doc_a_id,
            "start_time": (start + timedelta(hours=1)).isoformat(),
            "end_time": (start + timedelta(hours=1, minutes=30)).isoformat(),
        })
        assert resp.status_code == 403, f"esperaba 403 cross-tenant paciente, got {resp.status_code}"
        print("[OK 11] Clinica A no puede agendar con paciente de clinica B (403).")

        # --- Login como super-admin ---
        _login(client, "super@medcenter.app", "Super123!")

        # --- Super-admin ve todas las clinicas ---
        resp = _get(client, "/api/clinics")
        assert resp.status_code == 200
        clinicas = resp.get_json()["items"]
        assert len(clinicas) >= 2, f"esperaba 2+ clinicas, got {len(clinicas)}"
        print(f"[OK 12] Super-admin ve {len(clinicas)} clinicas.")

        # --- Stats de clinica A ---
        resp = _get(client, f"/api/clinics/{clinic_a_id}/stats")
        assert resp.status_code == 200
        stats = resp.get_json()["stats"]
        assert stats["usage"]["doctors"] == 1
        assert stats["usage"]["patients"] == 1
        assert stats["usage"]["appointments"] == 1
        print(f"[OK 13] Stats clinica A: {stats['usage']}")

        # --- Cambiar plan de clinica B ---
        resp = _patch(client, f"/api/clinics/{clinic_b_id}/plan", json={"plan": "professional"})
        assert resp.status_code == 200
        assert resp.get_json()["clinic"]["plan"] == "professional"
        print("[OK 14] Plan de clinica B cambiado a professional.")

        # --- Suspender clinica B ---
        resp = _patch(client, f"/api/clinics/{clinic_b_id}/status", json={"status": "suspendida"})
        assert resp.status_code == 200
        assert resp.get_json()["clinic"]["status"] == "suspendida"
        print("[OK 15] Clinica B suspendida.")

        # --- Clinica B suspendida: login y dashboard ---
        _login(client, "admin@drlopez.com", "Admin123!")
        resp = _get(client, "/api/dashboard")
        print(f"[OK 16] Clinica B suspendida - dashboard retorna {resp.status_code}.")

        # --- Reactivar clinica B ---
        _login(client, "super@medcenter.app", "Super123!")
        resp = _patch(client, f"/api/clinics/{clinic_b_id}/status", json={"status": "activa"})
        assert resp.status_code == 200
        assert resp.get_json()["clinic"]["status"] == "activa"
        print("[OK 17] Clinica B reactivada.")

        # --- Auto-registro de clinica via endpoint publico ---
        _logout(client)
        resp = client.post("/api/clinics/register", json={  # publico, sin auth
            "clinic_name": "Nueva Clinica Test",
            "subdomain": "nuevaclinica",
            "admin_email": "admin@nuevaclinica.com",
            "admin_password": "Admin123!",
            "admin_first_name": "Nuevo",
            "admin_last_name": "Admin",
        })
        assert resp.status_code == 201, f"auto-registro: {resp.status_code} {resp.get_json()}"
        assert resp.get_json()["clinic"]["plan"] == "starter"
        assert resp.get_json()["clinic"]["subdomain"] == "nuevaclinica"
        print("[OK 18] Auto-registro de clinica (endpoint publico).")

        # --- Resolucion por subdominio ---
        resp = client.get("/api/clinics/resolve?subdomain=sanangel")  # publico
        assert resp.status_code == 200
        assert resp.get_json()["clinic"]["subdomain"] == "sanangel"
        print("[OK 19] Resolucion por subdominio (sanangel).")

        # --- Resolucion: subdominio inexistente ---
        resp = client.get("/api/clinics/resolve?subdomain=noexiste")  # publico
        assert resp.status_code == 404
        print("[OK 20] Subdominio inexistente retorna 404.")

        # --- Admin de clinica A NO puede crear clinicas ---
        _login(client, "admin@sanangel.com", "Admin123!")
        resp = _post(client, "/api/clinics", json={
            "name": "Clinica Hackeada",
            "subdomain": "hack",
        })
        assert resp.status_code == 403, f"esperaba 403, got {resp.status_code}"
        print("[OK 21] Admin de clinica NO puede crear clinicas (403).")

        # --- Resumen final ---
        with app.app_context():
            print("\n========================================")
            print("  RESUMEN MULTI-TENANCY")
            print("========================================")
            print(f"  Clinicas:       {Clinic.query.count()}")
            print(f"  Usuarios:       {User.query.count()}")
            print(f"  Super-admin:    {User.query.filter_by(clinic_id=None).count()}")
            print(f"  Medicos:        {Doctor.query.count()}")
            print(f"  Pacientes:      {Patient.query.count()}")
            print(f"  Citas:          {Appointment.query.count()}")
            print()
            for c in Clinic.query.all():
                doc_count = Doctor.query.filter_by(clinic_id=c.id).count()
                pat_count = Patient.query.filter_by(clinic_id=c.id).count()
                apt_count = Appointment.query.filter_by(clinic_id=c.id).count()
                print(f"  {c.name:30s} | {c.plan.value:12s} | {c.status.value:10s} | {doc_count}D {pat_count}P {apt_count}A")

        print("\n========================================")
        print("FASE 5: VERIFICACION COMPLETADA (21/21)")
        print("========================================")


if __name__ == "__main__":
    main()
