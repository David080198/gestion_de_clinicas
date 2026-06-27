"""Verificacion integral de la Fase 6 - Sistema de Suscripciones.

Prueba el ciclo de vida completo de billing:
    1. Crear clinica + suscripcion con periodo de prueba.
    2. Verificar acceso durante el trial.
    3. Generar factura manual.
    4. Registrar pago -> factura pagada -> suscripcion activa.
    5. Cambiar plan (upgrade con prorrateo).
    6. Cambiar ciclo de cobro.
    7. Stats globales de billing (super-admin).
    8. Cancelar suscripcion -> clinica pierde acceso.
    9. Reactivar suscripcion.
    10. Webhook de pasarela de pago.
    11. Admin de clinica ve su suscripcion y facturas.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

os.environ["FLASK_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-phase6-billing"
os.environ["JWT_SECRET_KEY"] = "test-jwt-phase6"
os.environ["TEST_DATABASE_URL"] = "sqlite:///:memory:"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import (
    BillingCycle, Clinic, ClinicPlan, ClinicStatus, Invoice,
    InvoiceStatus, Payment, PaymentMethod, PaymentStatus,
    Subscription, SubscriptionStatus, User, UserRole,
)

UTC = timezone.utc

_current_token: str | None = None


def _login(client, email, password):
    global _current_token
    _current_token = None
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"login {email}: {resp.status_code}"
    body = resp.get_json()
    assert body["user"]["email"] == email
    _current_token = body.get("access_token")
    if not _current_token:
        set_cookie = resp.headers.get("Set-Cookie", "")
        for part in set_cookie.split(";"):
            part = part.strip()
            if part.startswith("access_token_cookie="):
                _current_token = part.split("=", 1)[1]
                break
    assert _current_token, "No se encontro token"


def _logout():
    global _current_token
    _current_token = None


def _h():
    if _current_token:
        return {"Authorization": f"Bearer {_current_token}"}
    return {}


def _get(client, path):
    return client.get(path, headers=_h())


def _post(client, path, json=None):
    return client.post(path, json=json, headers=_h())


def _patch(client, path, json=None):
    return client.patch(path, json=json, headers=_h())


def _delete(client, path):
    return client.delete(path, headers=_h())


def main():
    app = create_app("testing")
    app.config["JWT_COOKIE_SECURE"] = False
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    client = app.test_client()

    with app.app_context():
        db.create_all()

        # --- Super-admin ---
        sa = User(email="super@medcenter.app", first_name="Super", last_name="Admin",
                  role=UserRole.ADMIN, clinic_id=None)
        sa.set_password("Super123!")
        sa.save()
        print("[OK 01] Super-admin creado.")

        # --- Crear clinica ---
        _login(client, "super@medcenter.app", "Super123!")
        resp = _post(client, "/api/clinics", json={
            "name": "Clinica Test", "subdomain": "testclinic",
            "plan": "starter", "status": "activa",
        })
        assert resp.status_code == 201
        clinic_id = resp.get_json()["clinic"]["id"]
        print(f"[OK 02] Clinica creada (id={clinic_id}).")

        # --- Crear admin de clinica ---
        resp = _post(client, f"/api/clinics/{clinic_id}/admin", json={
            "email": "admin@testclinic.com", "password": "Admin123!",
            "first_name": "Admin", "last_name": "Clinic",
        })
        assert resp.status_code == 201
        print("[OK 03] Admin de clinica creado.")

        # ============================================================
        # 1. Crear suscripcion con periodo de prueba
        # ============================================================
        resp = _post(client, "/api/subscriptions", json={
            "clinic_id": clinic_id,
            "plan": "professional",
            "billing_cycle": "mensual",
        })
        assert resp.status_code == 201, f"crear sub: {resp.status_code} {resp.get_json()}"
        sub_id = resp.get_json()["subscription"]["id"]
        assert resp.get_json()["subscription"]["status"] == "prueba"
        assert resp.get_json()["subscription"]["is_trial"] == True
        assert resp.get_json()["subscription"]["is_active"] == True
        assert resp.get_json()["subscription"]["price"] == 3500.0
        print(f"[OK 04] Suscripcion creada (id={sub_id}, plan=professional, trial 14 dias).")

        # ============================================================
        # 2. Verificar acceso durante el trial
        # ============================================================
        sub = SubscriptionService_get_by_clinic(clinic_id)
        assert sub.is_active
        assert sub.is_trial
        print("[OK 05] Acceso permitido durante trial.")

        # ============================================================
        # 3. Generar factura manual
        # ============================================================
        resp = _post(client, f"/api/subscriptions/{sub_id}/invoice")
        assert resp.status_code == 201, f"generar factura: {resp.status_code} {resp.get_json()}"
        invoice_id = resp.get_json()["invoice"]["id"]
        invoice_number = resp.get_json()["invoice"]["number"]
        assert resp.get_json()["invoice"]["status"] == "emitida"
        assert resp.get_json()["invoice"]["amount"] == 3500.0
        assert resp.get_json()["invoice"]["balance_due"] == 3500.0
        print(f"[OK 06] Factura generada (id={invoice_id}, num={invoice_number}, $3500).")

        # ============================================================
        # 4. Registrar pago -> factura pagada -> suscripcion activa
        # ============================================================
        resp = _post(client, f"/api/subscriptions/invoices/{invoice_id}/pay", json={
            "amount": 3500.0,
            "method": "manual",
        })
        assert resp.status_code == 201, f"pago: {resp.status_code} {resp.get_json()}"
        assert resp.get_json()["payment"]["status"] == "completado"
        assert resp.get_json()["invoice"]["is_paid"] == True
        print("[OK 07] Pago registrado. Factura pagada.")

        # Verificar que la suscripcion esta activa
        resp = _get(client, f"/api/subscriptions/{sub_id}")
        assert resp.get_json()["subscription"]["status"] == "activa"
        assert resp.get_json()["subscription"]["is_trial"] == False
        print("[OK 08] Suscripcion activa tras pago.")

        # ============================================================
        # 5. Cambiar plan (upgrade con prorrateo)
        # ============================================================
        resp = _patch(client, f"/api/subscriptions/{sub_id}/plan", json={"plan": "clinic"})
        assert resp.status_code == 200, f"cambio plan: {resp.status_code} {resp.get_json()}"
        assert resp.get_json()["subscription"]["plan"] == "clinic"
        print("[OK 09] Plan cambiado a clinic (con prorrateo).")

        # Verificar que se genero factura de prorrateo
        resp = _get(client, f"/api/subscriptions/{sub_id}/invoices")
        invoices = resp.get_json()["items"]
        assert len(invoices) >= 2, f"esperaba 2+ facturas, got {len(invoices)}"
        print(f"[OK 10] Factura de prorrateo generada (total facturas: {len(invoices)}).")

        # ============================================================
        # 6. Cambiar ciclo de cobro
        # ============================================================
        resp = _patch(client, f"/api/subscriptions/{sub_id}/cycle", json={"billing_cycle": "anual"})
        assert resp.status_code == 200
        assert resp.get_json()["subscription"]["billing_cycle"] == "anual"
        print("[OK 11] Ciclo cambiado a anual.")

        # ============================================================
        # 7. Stats globales de billing
        # ============================================================
        resp = _get(client, "/api/subscriptions/stats")
        assert resp.status_code == 200
        stats = resp.get_json()["stats"]
        assert stats["total_subscriptions"] >= 1
        assert stats["active"] >= 1
        assert stats["monthly_revenue"] >= 3500.0
        print(f"[OK 12] Stats billing: MRR=${stats['mrr']}, revenue=${stats['monthly_revenue']}, active={stats['active']}")

        # ============================================================
        # 8. Cancelar suscripcion -> clinica pierde acceso
        # ============================================================
        resp = _delete(client, f"/api/subscriptions/{sub_id}")
        assert resp.status_code == 200
        assert resp.get_json()["subscription"]["status"] == "cancelada"
        print("[OK 13] Suscripcion cancelada.")

        # Verificar que la clinica esta cancelada
        clinic = Clinic.get_or_404(clinic_id)
        assert clinic.status == ClinicStatus.CANCELADA
        assert not clinic.is_active
        print("[OK 14] Clinica cancelada (sin acceso).")

        # ============================================================
        # 9. Crear nueva suscripcion (la anterior fue cancelada)
        # ============================================================
        resp = _post(client, "/api/subscriptions", json={
            "clinic_id": clinic_id,
            "plan": "starter",
            "billing_cycle": "mensual",
        })
        assert resp.status_code == 201, f"crear sub 2: {resp.status_code} {resp.get_json()}"
        sub_id = resp.get_json()["subscription"]["id"]
        print(f"[OK 15] Nueva suscripcion creada (id={sub_id}, plan=starter).")

        # ============================================================
        # 10. Webhook de pasarela de pago
        # ============================================================
        # Generar nueva factura
        resp = _post(client, f"/api/subscriptions/{sub_id}/invoice")
        assert resp.status_code == 201
        new_invoice = resp.get_json()["invoice"]
        new_invoice_number = new_invoice["number"]

        _logout()
        resp = client.post("/api/subscriptions/webhook", json={
            "type": "payment.succeeded",
            "data": {
                "invoice_number": new_invoice_number,
                "amount": 72000.0,  # plan clinic anual
                "transaction_id": "stripe_txn_12345",
            },
        })
        assert resp.status_code == 200, f"webhook: {resp.status_code} {resp.get_json()}"
        assert resp.get_json()["payment"]["status"] == "completado"
        print(f"[OK 16] Webhook de pago procesado (stripe_txn_12345).")

        # Verificar que la factura se pago
        inv = Invoice.get_by_number(new_invoice_number)
        assert inv.is_paid
        print("[OK 17] Factura pagada via webhook.")

        # ============================================================
        # 11. Admin de clinica ve su suscripcion y facturas
        # ============================================================
        _login(client, "admin@testclinic.com", "Admin123!")
        resp = _get(client, "/api/subscriptions/me")
        assert resp.status_code == 200
        assert resp.get_json()["subscription"]["plan"] == "starter"
        print("[OK 18] Admin ve su suscripcion.")

        resp = _get(client, "/api/subscriptions/me/invoices")
        assert resp.status_code == 200
        my_invoices = resp.get_json()["items"]
        assert len(my_invoices) >= 1
        print(f"[OK 19] Admin ve sus facturas ({len(my_invoices)} facturas).")

        # --- Resumen ---
        print("\n========================================")
        print("  RESUMEN SISTEMA DE SUSCRIPCIONES")
        print("========================================")
        with app.app_context():
            print(f"  Suscripciones: {Subscription.query.count()}")
            print(f"  Facturas:      {Invoice.query.count()}")
            print(f"  Pagos:         {Payment.query.count()}")
            for s in Subscription.query.all():
                c = Clinic.get_or_404(s.clinic_id)
                inv_count = Invoice.query.filter_by(subscription_id=s.id).count()
                paid = Invoice.query.filter_by(subscription_id=s.id, status=InvoiceStatus.PAGADA).count()
                print(f"  {c.name:20s} | plan={s.plan.value:12s} | status={s.status.value:15s} | {inv_count}F ({paid} pagadas)")
        print("========================================")
        print("FASE 6: VERIFICACION COMPLETADA (19/19)")
        print("========================================")


def SubscriptionService_get_by_clinic(clinic_id):
    from app.services.subscription_service import SubscriptionService
    return SubscriptionService.get_by_clinic(clinic_id)


if __name__ == "__main__":
    main()
