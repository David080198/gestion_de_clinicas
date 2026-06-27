"""Blueprint de suscripciones y facturacion.

Endpoints del super-admin:
    POST   /api/subscriptions                  - Crear suscripcion
    GET    /api/subscriptions                  - Listar suscripciones
    GET    /api/subscriptions/<id>             - Detalle
    PATCH  /api/subscriptions/<id>/plan        - Cambiar plan
    PATCH  /api/subscriptions/<id>/cycle       - Cambiar ciclo
    PATCH  /api/subscriptions/<id>/auto-renew  - Toggle auto-renovacion
    DELETE /api/subscriptions/<id>             - Cancelar
    POST   /api/subscriptions/<id>/reactivate  - Reactivar
    POST   /api/subscriptions/<id>/invoice     - Generar factura manual
    GET    /api/subscriptions/<id>/invoices    - Listar facturas
    GET    /api/subscriptions/stats            - Stats globales de billing

Endpoints del admin de clinica:
    GET    /api/subscriptions/me               - Mi suscripcion
    GET    /api/subscriptions/me/invoices      - Mis facturas
    POST   /api/invoices/<id>/pay              - Registrar pago manual

Endpoint publico (webhook de pasarela):
    POST   /api/subscriptions/webhook          - Webhook Stripe/Conekta
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from app.exceptions import ValidationError
from app.models import (
    BillingCycle,
    ClinicPlan,
    Invoice,
    InvoiceStatus,
    PaymentMethod,
)
from app.schemas.subscription_schemas import (
    ChangeCycleSchema,
    ChangePlanSchema,
    InvoiceSchema,
    PaymentCreateSchema,
    PaymentSchema,
    SubscriptionCreateSchema,
    SubscriptionSchema,
    SubscriptionUpdateSchema,
)
from app.services.subscription_service import SubscriptionService
from app.utils.decorators import super_admin_only, login_required, current_user
from app.utils.tenant import current_clinic_id

subscriptions_bp: Blueprint = Blueprint("subscriptions", __name__)

# Schemas
_create_schema = SubscriptionCreateSchema()
_update_schema = SubscriptionUpdateSchema()
_plan_schema = ChangePlanSchema()
_cycle_schema = ChangeCycleSchema()
_sub_schema = SubscriptionSchema()
_sub_schema_many = SubscriptionSchema(many=True)
_invoice_schema = InvoiceSchema()
_invoice_schema_many = InvoiceSchema(many=True)
_payment_schema = PaymentSchema()
_payment_create_schema = PaymentCreateSchema()


# ============================================================
# Endpoints del super-admin
# ============================================================

@subscriptions_bp.route("", methods=["POST"])
@super_admin_only
def create_subscription():
    """Crea una suscripcion para una clinica."""
    payload: dict[str, Any] = _parse_json(_create_schema)
    sub = SubscriptionService.create_subscription(
        clinic_id=payload["clinic_id"],
        plan=payload.get("plan", ClinicPlan.STARTER),
        billing_cycle=payload.get("billing_cycle", BillingCycle.MENSUAL),
        auto_renew=payload.get("auto_renew", True),
        price_override=payload.get("price_override"),
    )
    return jsonify({
        "message": "Suscripcion creada con periodo de prueba.",
        "subscription": _sub_schema.dump(sub),
    }), 201


@subscriptions_bp.route("", methods=["GET"])
@super_admin_only
def list_subscriptions():
    """Lista todas las suscripciones."""
    from app.models import Subscription
    from app.extensions import db

    subs = list(db.session.scalars(
        db.select(Subscription).order_by(Subscription.created_at.desc())
    ))
    return jsonify({"items": _sub_schema_many.dump(subs)})


@subscriptions_bp.route("/stats", methods=["GET"])
@super_admin_only
def billing_stats():
    """Estadisticas globales de facturacion."""
    stats = SubscriptionService.get_billing_stats()
    return jsonify({"stats": stats})


@subscriptions_bp.route("/<int:sub_id>", methods=["GET"])
@super_admin_only
def get_subscription(sub_id: int):
    """Detalle de una suscripcion."""
    sub = SubscriptionService.get_or_404(sub_id)
    return jsonify({"subscription": _sub_schema.dump(sub)})


@subscriptions_bp.route("/<int:sub_id>/plan", methods=["PATCH"])
@super_admin_only
def change_plan(sub_id: int):
    """Cambia el plan de una suscripcion."""
    payload: dict[str, Any] = _parse_json(_plan_schema)
    sub = SubscriptionService.change_plan(sub_id, payload["plan"])
    return jsonify({
        "message": f"Plan cambiado a {sub.plan.value}.",
        "subscription": _sub_schema.dump(sub),
    })


@subscriptions_bp.route("/<int:sub_id>/cycle", methods=["PATCH"])
@super_admin_only
def change_cycle(sub_id: int):
    """Cambia el ciclo de cobro."""
    payload: dict[str, Any] = _parse_json(_cycle_schema)
    sub = SubscriptionService.change_billing_cycle(sub_id, payload["billing_cycle"])
    return jsonify({
        "message": f"Ciclo cambiado a {sub.billing_cycle.value}.",
        "subscription": _sub_schema.dump(sub),
    })


@subscriptions_bp.route("/<int:sub_id>/auto-renew", methods=["PATCH"])
@super_admin_only
def toggle_auto_renew(sub_id: int):
    """Activa/desactiva la auto-renovacion."""
    sub = SubscriptionService.get_or_404(sub_id)
    sub.auto_renew = not sub.auto_renew
    from app.extensions import db
    db.session.commit()
    return jsonify({
        "message": f"Auto-renovacion {'activada' if sub.auto_renew else 'desactivada'}.",
        "subscription": _sub_schema.dump(sub),
    })


@subscriptions_bp.route("/<int:sub_id>", methods=["DELETE"])
@super_admin_only
def cancel_subscription(sub_id: int):
    """Cancela una suscripcion."""
    sub = SubscriptionService.cancel_subscription(sub_id)
    return jsonify({
        "message": "Suscripcion cancelada.",
        "subscription": _sub_schema.dump(sub),
    })


@subscriptions_bp.route("/<int:sub_id>/reactivate", methods=["POST"])
@super_admin_only
def reactivate_subscription(sub_id: int):
    """Reactiva una suscripcion suspendida."""
    sub = SubscriptionService.reactivate_subscription(sub_id)
    return jsonify({
        "message": "Suscripcion reactivada. Genera el pago para activar.",
        "subscription": _sub_schema.dump(sub),
    })


@subscriptions_bp.route("/<int:sub_id>/invoice", methods=["POST"])
@super_admin_only
def generate_invoice(sub_id: int):
    """Genera una factura manual para el siguiente periodo."""
    invoice = SubscriptionService.generate_invoice(sub_id)
    return jsonify({
        "message": "Factura generada.",
        "invoice": _invoice_schema.dump(invoice),
    }), 201


@subscriptions_bp.route("/<int:sub_id>/invoices", methods=["GET"])
@super_admin_only
def list_subscription_invoices(sub_id: int):
    """Lista las facturas de una suscripcion."""
    invoices = SubscriptionService.list_invoices(sub_id)
    return jsonify({"items": _invoice_schema_many.dump(invoices)})


# ============================================================
# Endpoints del admin de clinica (su propia suscripcion)
# ============================================================

@subscriptions_bp.route("/me", methods=["GET"])
@login_required
def my_subscription():
    """El admin de la clinica ve su propia suscripcion."""
    clinic_id = current_clinic_id()
    if clinic_id is None:
        raise ValidationError("Tu cuenta no pertenece a ninguna clinica.")
    try:
        sub = SubscriptionService.get_by_clinic(clinic_id)
        return jsonify({"subscription": _sub_schema.dump(sub)})
    except Exception as e:
        return jsonify({"subscription": None, "message": "Sin suscripcion activa."}), 404


@subscriptions_bp.route("/me/invoices", methods=["GET"])
@login_required
def my_invoices():
    """El admin de la clinica ve sus facturas."""
    clinic_id = current_clinic_id()
    if clinic_id is None:
        raise ValidationError("Tu cuenta no pertenece a ninguna clinica.")
    invoices = SubscriptionService.list_clinic_invoices(clinic_id)
    return jsonify({"items": _invoice_schema_many.dump(invoices)})


# ============================================================
# Pagos
# ============================================================

@subscriptions_bp.route("/invoices/<int:invoice_id>/pay", methods=["POST"])
@login_required
def pay_invoice(invoice_id: int):
    """Registra un pago sobre una factura.

    El admin de la clinica puede registrar un pago manual o confirmar
    un pago via pasarela.
    """
    from app.extensions import db
    from app.models import Invoice
    from app.utils.tenant import assert_resource_belongs_to_clinic

    invoice: Invoice | None = db.session.get(Invoice, invoice_id)
    if invoice is None:
        from app.exceptions import RecordNotFoundError
        raise RecordNotFoundError(f"Factura {invoice_id} no encontrada.")
    assert_resource_belongs_to_clinic(invoice, "factura")

    payload: dict[str, Any] = _parse_json(_payment_create_schema)
    payment = SubscriptionService.register_payment(
        invoice_id=invoice_id,
        amount=payload["amount"],
        method=payload.get("method", PaymentMethod.MANUAL),
        transaction_id=payload.get("transaction_id"),
    )
    return jsonify({
        "message": "Pago registrado.",
        "payment": _payment_schema.dump(payment),
        "invoice": _invoice_schema.dump(db.session.get(Invoice, invoice_id)),
    }), 201


# ============================================================
# Webhook de pasarela de pago (publico)
# ============================================================

@subscriptions_bp.route("/webhook", methods=["POST"])
def payment_webhook():
    """Webhook para recibir notificaciones de Stripe/Conekta.

    Este endpoint es llamado por la pasarela de pago cuando se procesa
    un pago. No requiere autenticacion (la pasarela envia su propio
    mecanismo de verificacion).

    Formato esperado (simplificado):
        {
            "type": "payment.succeeded",
            "data": {
                "transaction_id": "txn_123",
                "invoice_number": "INV-2026-ABCD",
                "amount": 3500.00
            }
        }
    """
    payload = request.get_json(silent=True)
    if payload is None:
        raise ValidationError("El cuerpo debe ser JSON.")

    event_type: str = payload.get("type", "")
    data: dict = payload.get("data", {})

    if event_type == "payment.succeeded":
        invoice_number: str | None = data.get("invoice_number")
        amount: float | None = data.get("amount")
        transaction_id: str | None = data.get("transaction_id")

        if not invoice_number or amount is None:
            raise ValidationError("Se requiere invoice_number y amount.")

        try:
            invoice: Invoice = Invoice.get_by_number(invoice_number)
        except Exception:
            return jsonify({"message": "Factura no encontrada.", "ignored": True}), 404

        payment = SubscriptionService.register_payment(
            invoice_id=invoice.id,
            amount=amount,
            method=PaymentMethod.STRIPE,
            transaction_id=transaction_id,
            gateway_response=str(payload),
        )
        return jsonify({
            "message": "Pago procesado.",
            "payment": _payment_schema.dump(payment),
        }), 200

    elif event_type == "subscription.cancelled":
        # La pasarela notifica cancelacion
        clinic_id: int | None = data.get("clinic_id")
        if clinic_id:
            try:
                sub = SubscriptionService.get_by_clinic(clinic_id)
                SubscriptionService.cancel_subscription(sub.id)
            except Exception:
                pass
        return jsonify({"message": "Cancelacion procesada."}), 200

    return jsonify({"message": "Evento no reconocido.", "type": event_type}), 200


# ============================================================
# Helper
# ============================================================

def _parse_json(schema, partial: bool = False) -> dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("El cuerpo de la peticion debe ser JSON.")
    return schema.load(data, partial=partial)
