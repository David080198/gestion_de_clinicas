"""Blueprint de integracion con Stripe.

Endpoints:
    GET  /api/stripe/config              - Publishable key (publico)
    POST /api/stripe/checkout-session    - Crear sesion de checkout
    POST /api/stripe/customer-portal     - Portal de gestion de pago
    POST /api/stripe/webhook             - Webhook de Stripe (publico)
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request

from app.exceptions import ValidationError
from app.models import BillingCycle, Clinic, ClinicPlan
from app.services.stripe_service import StripeService
from app.utils.decorators import login_required
from app.utils.tenant import current_clinic_id

stripe_bp: Blueprint = Blueprint("stripe", __name__, url_prefix="/api/stripe")


@stripe_bp.route("/config", methods=["GET"])
def get_config():
    """Retorna la publishable key de Stripe (segura para frontend)."""
    pk: str = current_app.config.get("STRIPE_PUBLISHABLE_KEY", "")
    if not pk:
        raise ValidationError("STRIPE_PUBLISHABLE_KEY no esta configurada.")
    return jsonify({"publishable_key": pk})


@stripe_bp.route("/checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    """Crea una sesion de checkout de Stripe para la clinica actual.

    Body JSON:
        {
            "plan": "professional",
            "billing_cycle": "mensual",
            "success_url": "https://tudominio.com/success?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "https://tudominio.com/cancel"
        }
    """
    clinic_id: int | None = current_clinic_id()
    if clinic_id is None:
        raise ValidationError("Tu cuenta no pertenece a ninguna clinica.")

    clinic: Clinic = Clinic.get_or_404(clinic_id)
    data: dict[str, Any] = request.get_json(silent=True) or {}

    plan_value: str = data.get("plan", "starter")
    cycle_value: str = data.get("billing_cycle", "mensual")
    success_url: str = data.get("success_url", "")
    cancel_url: str = data.get("cancel_url", "")

    if not success_url or not cancel_url:
        raise ValidationError("Se requieren success_url y cancel_url.")

    try:
        plan = ClinicPlan[plan_value.upper()]
        billing_cycle = BillingCycle[cycle_value.upper()]
    except KeyError as exc:
        raise ValidationError(f"Plan o ciclo invalido: {exc}") from exc

    # Usar el email del admin de la clinica
    admin = clinic.users[0] if clinic.users else None
    email: str = admin.email if admin else clinic.email or ""
    name: str = clinic.name

    result = StripeService.create_checkout_session(
        clinic=clinic,
        email=email,
        name=name,
        plan=plan,
        billing_cycle=billing_cycle,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    return jsonify(result), 201


@stripe_bp.route("/customer-portal", methods=["POST"])
@login_required
def customer_portal():
    """Crea una sesion del portal de cliente de Stripe.

    Body JSON:
        {"return_url": "https://tudominio.com/settings"}
    """
    clinic_id: int | None = current_clinic_id()
    if clinic_id is None:
        raise ValidationError("Tu cuenta no pertenece a ninguna clinica.")

    clinic: Clinic = Clinic.get_or_404(clinic_id)
    data: dict[str, Any] = request.get_json(silent=True) or {}
    return_url: str = data.get("return_url", "")

    if not return_url:
        raise ValidationError("Se requiere return_url.")

    result = StripeService.create_customer_portal_session(
        clinic=clinic,
        return_url=return_url,
    )
    return jsonify(result), 201


@stripe_bp.route("/webhook", methods=["POST"])
def webhook():
    """Recibe webhooks de Stripe.

    Stripe envia un payload firmado en el cuerpo de la peticion.
    La firma se valida con STRIPE_WEBHOOK_SECRET.
    """
    payload: bytes = request.get_data()
    sig_header: str | None = request.headers.get("Stripe-Signature")

    event = StripeService.construct_event(payload, sig_header)
    event_type: str = event.get("type", "")
    event_data: dict[str, Any] = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        result = StripeService.handle_checkout_session_completed(event_data)
    elif event_type == "invoice.payment_succeeded":
        result = StripeService.handle_invoice_payment_succeeded(event_data)
    elif event_type == "invoice.payment_failed":
        result = StripeService.handle_invoice_payment_failed(event_data)
    elif event_type == "customer.subscription.deleted":
        result = StripeService.handle_subscription_deleted(event_data)
    else:
        result = {"message": f"Evento {event_type} recibido pero no procesado."}

    return jsonify(result), 200
