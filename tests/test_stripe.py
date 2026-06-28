"""Tests de integracion con Stripe (con mocks)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.models import ClinicPlan


@pytest.fixture
def stripe_configured(app):
    """Configura variables de Stripe para testing."""
    app.config["STRIPE_SECRET_KEY"] = "sk_test_123"
    app.config["STRIPE_PUBLISHABLE_KEY"] = "pk_test_123"
    app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_123"
    app.config["STRIPE_PRICE_STARTER_MONTHLY"] = "price_starter_monthly"
    app.config["STRIPE_PRICE_STARTER_YEARLY"] = "price_starter_yearly"
    app.config["STRIPE_PRICE_PROFESSIONAL_MONTHLY"] = "price_professional_monthly"
    app.config["STRIPE_PRICE_PROFESSIONAL_YEARLY"] = "price_professional_yearly"
    app.config["STRIPE_PRICE_CLINIC_MONTHLY"] = "price_clinic_monthly"
    app.config["STRIPE_PRICE_CLINIC_YEARLY"] = "price_clinic_yearly"


def test_stripe_config_endpoint(client, app, stripe_configured):
    resp = client.get("/api/stripe/config")
    assert resp.status_code == 200
    assert resp.get_json()["publishable_key"] == "pk_test_123"


def test_stripe_config_endpoint_fails_without_key(client, app):
    app.config["STRIPE_PUBLISHABLE_KEY"] = ""
    resp = client.get("/api/stripe/config")
    assert resp.status_code == 400


def test_create_checkout_session(client, app, admin_user, stripe_configured):
    from app.models import Clinic
    from app.extensions import db

    with app.app_context():
        clinic = Clinic(name="Test Clinic", slug="test-clinic", subdomain="test-clinic")
        clinic.save()
        admin_user.clinic_id = clinic.id
        db.session.commit()

    client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "Admin123!"},
    )

    mock_session = MagicMock()
    mock_session.id = "cs_test_123"
    mock_session.url = "https://checkout.stripe.com/test"

    mock_customer = MagicMock()
    mock_customer.id = "cus_test_123"

    with patch("app.services.stripe_service.stripe.Customer.create", return_value=mock_customer), \
         patch("app.services.stripe_service.stripe.checkout.Session.create", return_value=mock_session):
        resp = client.post(
            "/api/stripe/checkout-session",
            json={
                "plan": "professional",
                "billing_cycle": "mensual",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data["session_id"] == "cs_test_123"
    assert data["checkout_url"] == "https://checkout.stripe.com/test"
    assert data["customer_id"] == "cus_test_123"


def test_webhook_checkout_completed(client, app, stripe_configured):
    from app.models import Clinic

    with app.app_context():
        clinic = Clinic(name="Webhook Clinic", slug="webhook-clinic", subdomain="webhook-clinic")
        clinic.save()
        clinic_id = clinic.id

    mock_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "subscription": "sub_test_123",
                "customer": "cus_test_123",
                "metadata": {
                    "clinic_id": str(clinic_id),
                    "plan": "professional",
                    "billing_cycle": "mensual",
                },
            }
        },
    }

    mock_subscription = {
        "id": "sub_test_123",
        "current_period_start": 1700000000,
        "current_period_end": 1702592000,
        "items": {"data": [{"price": {"id": "price_professional_monthly"}}]},
    }

    with patch("app.services.stripe_service.stripe.Webhook.construct_event", return_value=mock_event), \
         patch("app.services.stripe_service.stripe.Subscription.retrieve", return_value=mock_subscription):
        resp = client.post(
            "/api/stripe/webhook",
            data=b"payload",
            headers={"Stripe-Signature": "sig_test"},
        )

    assert resp.status_code == 200
    assert "Suscripcion activada" in resp.get_json()["message"]


def test_webhook_unsupported_event(client, app, stripe_configured):
    mock_event = {
        "type": "charge.refunded",
        "data": {"object": {"id": "ch_test"}},
    }

    with patch("app.services.stripe_service.stripe.Webhook.construct_event", return_value=mock_event):
        resp = client.post(
            "/api/stripe/webhook",
            data=b"payload",
            headers={"Stripe-Signature": "sig_test"},
        )

    assert resp.status_code == 200
    assert "no procesado" in resp.get_json()["message"]
