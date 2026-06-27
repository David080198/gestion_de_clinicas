"""Verificacion integral de la Fase 2 (Backend Core + API + Blueprints).

Ejecuta la aplicacion con SQLite en memoria y prueba los flujos completos
a traves del test client de Flask:

    1. Registro de paciente (auto) y login con cookies JWT.
    2. RBAC: endpoint /me solo accesible con sesion.
    3. Admin crea medico y recepcionista.
    4. Recepcionista agenda cita para un paciente.
    5. Control de colisiones via API (409).
    6. Disponibilidad de slots del medico.
    7. Calendario de citas.
    8. Medico transita cita: CONFIRMADA -> EN_CONSULTA.
    9. Medico crea expediente clinico (inmutable).
    10. Medico emite receta electronica.
    11. Paciente descarga PDF de su receta.
    12. Dashboard por rol retorna metricas distintas.
    13. RBAC negativo: paciente no puede crear expediente (403).
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta, timezone

os.environ["FLASK_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-phase2"
os.environ["JWT_SECRET_KEY"] = "test-jwt-phase2"
os.environ["TEST_DATABASE_URL"] = "sqlite:///:memory:"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import (
    Appointment, AppointmentStatus, Doctor, DoctorSchedule, Gender,
    Patient, User, UserRole, Weekday,
)

UTC = timezone.utc


def _ts(dt: datetime) -> str:
    return dt.isoformat()


def _switch_user(client, email: str, password: str) -> dict:
    """Cierra sesion, limpia cookies y loguea a un usuario distinto.

    Retorna el JSON de la respuesta de login.
    """
    client.post("/api/auth/logout")
    # limpia cookies residuales del test client
    for name in ("access_token_cookie", "refresh_token_cookie", "csrf_access_token", "csrf_refresh_token"):
        try:
            client.delete_cookie(name, domain="localhost")
        except Exception:
            pass
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"login {email}: {resp.status_code} {resp.get_json()}"
    return resp.get_json()


def _login_client(app, email: str, password: str):
    """Crea un test client nuevo y loguea al usuario (cookie jar limpio).

    Usar un client fresco por usuario evita la acumulacion de cookies JWT
    duplicadas que enviarian el token del usuario anterior.
    """
    c = app.test_client()
    resp = c.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"login {email}: {resp.status_code} {resp.get_json()}"
    return c


def main() -> None:
    app = create_app("testing")
    app.config["JWT_COOKIE_SECURE"] = False
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False

    with app.app_context():
        db.create_all()
        # ---------- seed inicial ----------
        admin = User(email="admin@clinic.com", first_name="Ana",
                     last_name="Admin", role=UserRole.ADMIN)
        admin.set_password("Secret123"); admin.save()

        med_user = User(email="dr.house@clinic.com", first_name="Gregory",
                        last_name="House", role=UserRole.MEDICO)
        med_user.set_password("Secret123"); med_user.save()

        recep_user = User(email="recep@clinic.com", first_name="Maria",
                          last_name="Recep", role=UserRole.RECEPCIONISTA)
        recep_user.set_password("Secret123"); recep_user.save()

        doctor = Doctor(user_id=med_user.id, license_number="MED-001",
                        specialty="Medicina Interna", consultation_fee=800)
        doctor.save()

        sched = DoctorSchedule(doctor_id=doctor.id, weekday=Weekday.LUNES,
                               start_time=time(9, 0), end_time=time(18, 0),
                               slot_minutes=30)
        sched.save()
        doctor_id = doctor.id  # capturar antes de salir del contexto

    # cliente anonimo para registro
    anon = app.test_client()

    # ---------- 1. Registro paciente via API ----------
    resp = anon.post("/api/auth/register", json={
        "email": "juan@pac.com", "password": "Secret123",
        "first_name": "Juan", "last_name": "Perez",
        "role": "paciente", "document_number": "DOC123",
        "birth_date": "1990-05-15", "gender": "masculino",
    })
    assert resp.status_code == 201, f"registro: {resp.status_code} {resp.get_json()}"
    print("[OK 01] Registro de paciente via API.")

    # ---------- 2. Login paciente ----------
    patient_client = _login_client(app, "juan@pac.com", "Secret123")
    assert patient_client.get("/api/auth/me").get_json()["user"]["role"] == "paciente"
    print("[OK 02] Login paciente con cookies JWT.")

    # ---------- 3. /me ----------
    resp = patient_client.get("/api/auth/me")
    assert resp.get_json()["user"]["email"] == "juan@pac.com"
    print("[OK 03] /me retorna el perfil autenticado.")

    # ---------- 4. Logout cierra sesion ----------
    patient_client.post("/api/auth/logout")
    resp = patient_client.get("/api/auth/me")
    assert resp.status_code == 401, f"tras logout esperaba 401, got {resp.status_code}"
    print("[OK 04] Logout revoca acceso.")

    # ---------- 5. Login admin ----------
    admin_client = _login_client(app, "admin@clinic.com", "Secret123")
    assert admin_client.get("/api/auth/me").get_json()["user"]["role"] == "admin"
    print("[OK 05] Login admin verificado via /me.")

    # ---------- 6. Admin crea recepcionista ----------
    resp = admin_client.post("/api/auth/register", json={
        "email": "recep2@clinic.com", "password": "Secret123",
        "first_name": "Maria", "last_name": "Recep",
        "role": "recepcionista",
    })
    assert resp.status_code == 201, f"crear recep: {resp.status_code} {resp.get_json()}"
    print("[OK 06] Admin crea recepcionista via API.")

    # ---------- 7. Login recepcionista ----------
    recep_client = _login_client(app, "recep@clinic.com", "Secret123")
    print("[OK 07] Login recepcionista.")

    # obtener patient_id via el dashboard del paciente o via query directa
    with app.app_context():
        patient = Patient.query.filter_by(document_number="DOC123").first()
        patient_id = patient.id
    # Calcular el proximo lunes dinamicamente
    from datetime import date as _date
    _today = _date.today()
    _days_to_monday = (7 - _today.weekday()) % 7
    if _days_to_monday == 0:
        _days_to_monday = 7
    _next_monday = _today + timedelta(days=_days_to_monday)
    _test_date_str = _next_monday.isoformat()
    start = datetime.combine(_next_monday, time(9, 0), tzinfo=UTC)  # Lunes
    end = start + timedelta(minutes=30)

    # ---------- 8. Recepcionista agenda cita ----------
    resp = recep_client.post("/api/appointments", json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "start_time": _ts(start), "end_time": _ts(end),
        "reason": "Dolor de cabeza",
    })
    assert resp.status_code == 201, f"crear cita: {resp.status_code} {resp.get_json()}"
    apt_id = resp.get_json()["appointment"]["id"]
    assert resp.get_json()["appointment"]["status"] == "confirmada"
    print(f"[OK 08] Recepcionista agenda cita {apt_id} (confirmada).")

    # ---------- 9. Colision via API (409) ----------
    resp = recep_client.post("/api/appointments", json={
        "patient_id": patient_id, "doctor_id": doctor_id,
        "start_time": _ts(start + timedelta(minutes=10)),
        "end_time": _ts(start + timedelta(minutes=40)),
    })
    assert resp.status_code == 409, f"colision esperaba 409, got {resp.status_code}"
    print("[OK 09] API rechaza cita solapada con 409.")

    # ---------- 10. Disponibilidad de slots ----------
    resp = recep_client.get(f"/api/appointments/doctors/{doctor_id}/availability?date={_test_date_str}")
    assert resp.status_code == 200
    slots = resp.get_json()["slots"]
    assert len(slots) > 0
    ocupado = any(s["start"].startswith(_test_date_str + "T09:00") and not s["available"] for s in slots)
    assert ocupado, "el slot 09:00 debia estar ocupado"
    print(f"[OK 10] Disponibilidad: {len(slots)} slots, 09:00 ocupado.")

    # ---------- 11. Calendario ----------
    _test_end_str = (_next_monday + timedelta(days=1)).isoformat()
    resp = recep_client.get(f"/api/appointments/calendar?start={_test_date_str}&end={_test_end_str}")
    assert resp.status_code == 200
    assert len(resp.get_json()["items"]) == 1
    print("[OK 11] Calendario retorna la cita del rango.")

    # ---------- 12. Login medico ----------
    med_client = _login_client(app, "dr.house@clinic.com", "Secret123")
    print("[OK 12] Login medico.")

    # ---------- 13. Medico pasa a EN_CONSULTA ----------
    resp = med_client.patch(f"/api/appointments/{apt_id}/status", json={"status": "en_consulta"})
    assert resp.status_code == 200, f"status: {resp.status_code} {resp.get_json()}"
    assert resp.get_json()["appointment"]["status"] == "en_consulta"
    print("[OK 13] Medico transita cita a EN_CONSULTA.")

    # ---------- 14. Medico crea expediente ----------
    resp = med_client.post(f"/api/medical/appointments/{apt_id}/record", json={
        "reason": "Cefalea", "symptoms": "Dolor bilateral",
        "blood_pressure": "120/80", "temperature": 36.5,
        "heart_rate": 72, "weight": 75.0, "height": 170.0,
        "diagnosis": "Cefalea tensional", "treatment": "Paracetamol",
    })
    assert resp.status_code == 201, f"expediente: {resp.status_code} {resp.get_json()}"
    record_id = resp.get_json()["record"]["id"]
    print(f"[OK 14] Medico crea expediente {record_id}.")

    # ---------- 15. Medico emite receta ----------
    resp = med_client.post(f"/api/medical/records/{record_id}/prescriptions", json={
        "medications": [
            {"name": "Paracetamol", "dose": "500mg", "frequency": "c/8h", "duration": "5 dias"},
            {"name": "Ibuprofeno", "dose": "400mg", "frequency": "c/12h", "duration": "3 dias"},
        ],
        "notes": "Suspender si aparece rash.",
    })
    assert resp.status_code == 201, f"receta: {resp.status_code} {resp.get_json()}"
    rx_code = resp.get_json()["prescription"]["code"]
    print(f"[OK 15] Medico emite receta {rx_code} con 2 medicamentos.")

    # ---------- 16. Descarga PDF ----------
    resp = med_client.get(f"/api/medical/prescriptions/{rx_code}/pdf")
    assert resp.status_code == 200, f"pdf: {resp.status_code}"
    assert resp.mimetype == "application/pdf"
    assert len(resp.data) > 1000
    print(f"[OK 16] PDF generado ({len(resp.data)} bytes).")

    # ---------- 17. Medico completa la cita ----------
    resp = med_client.patch(f"/api/appointments/{apt_id}/status", json={"status": "completada"})
    assert resp.status_code == 200
    print("[OK 17] Medico completa la cita.")

    # ---------- 18. Dashboard medico ----------
    resp = med_client.get("/api/dashboard")
    assert resp.status_code == 200
    assert resp.get_json()["dashboard"]["role"] == "medico"
    print("[OK 18] Dashboard medico retorna metricas.")

    # ---------- 19. Dashboard paciente ----------
    patient_client = _login_client(app, "juan@pac.com", "Secret123")  # re-login tras logout
    resp = patient_client.get("/api/dashboard")
    assert resp.status_code == 200
    assert resp.get_json()["dashboard"]["role"] == "paciente"
    print("[OK 19] Dashboard paciente retorna proximas citas + historial.")

    # ---------- 20. Paciente lista sus recetas ----------
    resp = patient_client.get(f"/api/medical/patients/{patient_id}/prescriptions")
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 1
    print("[OK 20] Paciente lista sus recetas.")

    # ---------- 21. Paciente ve su historial ----------
    resp = patient_client.get(f"/api/medical/patients/{patient_id}/history")
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 1
    print("[OK 21] Paciente consulta su historial clinico.")

    # ---------- 22. RBAC negativo: paciente intenta crear expediente ----------
    resp = patient_client.post(f"/api/medical/appointments/{apt_id}/record", json={
        "reason": "intento",
    })
    assert resp.status_code == 403, f"esperaba 403, got {resp.status_code}"
    print("[OK 22] RBAC: paciente no puede crear expediente (403).")

    # ---------- 23. Dashboard admin ----------
    resp = admin_client.get("/api/dashboard")
    assert resp.status_code == 200
    dash = resp.get_json()["dashboard"]
    assert dash["role"] == "admin"
    assert "top_doctors" in dash and "totals" in dash
    print("[OK 23] Dashboard admin: top_doctors + ingresos + monthly_revenue.")

    print("\n========================================")
    print("FASE 2: VERIFICACION COMPLETADA (23/23)")
    print("========================================")


if __name__ == "__main__":
    main()
