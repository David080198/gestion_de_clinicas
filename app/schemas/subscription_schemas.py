"""Schemas de suscripciones y facturacion."""

from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.models import BillingCycle, ClinicPlan, InvoiceStatus, PaymentMethod, BillingPaymentStatus, SubscriptionStatus


class SubscriptionCreateSchema(Schema):
    """Payload para crear una suscripcion."""

    clinic_id = fields.Integer(required=True)
    plan = fields.Enum(ClinicPlan, by_value=True, load_default=ClinicPlan.STARTER)
    billing_cycle = fields.Enum(BillingCycle, by_value=True, load_default=BillingCycle.MENSUAL)
    auto_renew = fields.Boolean(load_default=True)
    price_override = fields.Decimal(load_default=None, as_string=True, places=2, allow_none=True)


class SubscriptionUpdateSchema(Schema):
    """Payload para actualizar una suscripcion."""

    billing_cycle = fields.Enum(BillingCycle, by_value=True, required=False)
    auto_renew = fields.Boolean(required=False)


class ChangePlanSchema(Schema):
    """Payload para cambiar de plan."""

    plan = fields.Enum(ClinicPlan, by_value=True, required=True)


class ChangeCycleSchema(Schema):
    """Payload para cambiar ciclo de cobro."""

    billing_cycle = fields.Enum(BillingCycle, by_value=True, required=True)


class SubscriptionSchema(Schema):
    """Schema de salida de una suscripcion."""

    id = fields.Integer(dump_only=True)
    clinic_id = fields.Integer(dump_only=True)
    plan = fields.Enum(ClinicPlan, by_value=True, dump_only=True)
    billing_cycle = fields.Enum(BillingCycle, by_value=True, dump_only=True)
    status = fields.Enum(SubscriptionStatus, by_value=True, dump_only=True)
    started_at = fields.DateTime(dump_only=True, format="iso")
    trial_ends_at = fields.DateTime(dump_only=True, format="iso", allow_none=True)
    current_period_start = fields.DateTime(dump_only=True, format="iso", allow_none=True)
    current_period_end = fields.DateTime(dump_only=True, format="iso", allow_none=True)
    auto_renew = fields.Boolean(dump_only=True)
    cancelled_at = fields.DateTime(dump_only=True, format="iso", allow_none=True)
    price = fields.Float(dump_only=True)
    is_active = fields.Boolean(dump_only=True)
    is_trial = fields.Boolean(dump_only=True)
    trial_expired = fields.Boolean(dump_only=True)
    period_expired = fields.Boolean(dump_only=True)
    days_until_expiry = fields.Integer(dump_only=True, allow_none=True)


class InvoiceSchema(Schema):
    """Schema de salida de una factura."""

    id = fields.Integer(dump_only=True)
    number = fields.Str(dump_only=True)
    subscription_id = fields.Integer(dump_only=True)
    clinic_id = fields.Integer(dump_only=True)
    amount = fields.Float(dump_only=True)
    currency = fields.Str(dump_only=True)
    status = fields.Enum(InvoiceStatus, by_value=True, dump_only=True)
    period_start = fields.DateTime(dump_only=True, format="iso")
    period_end = fields.DateTime(dump_only=True, format="iso")
    issue_date = fields.DateTime(dump_only=True, format="iso")
    due_date = fields.DateTime(dump_only=True, format="iso")
    paid_date = fields.DateTime(dump_only=True, format="iso", allow_none=True)
    is_paid = fields.Boolean(dump_only=True)
    is_overdue = fields.Boolean(dump_only=True)
    total_paid = fields.Float(dump_only=True)
    balance_due = fields.Float(dump_only=True)
    notes = fields.Str(dump_only=True, allow_none=True)


class PaymentSchema(Schema):
    """Schema de salida de un pago."""

    id = fields.Integer(dump_only=True)
    invoice_id = fields.Integer(dump_only=True)
    amount = fields.Float(dump_only=True)
    currency = fields.Str(dump_only=True)
    method = fields.Enum(PaymentMethod, by_value=True, dump_only=True)
    status = fields.Enum(BillingPaymentStatus, by_value=True, dump_only=True)
    transaction_id = fields.Str(dump_only=True, allow_none=True)
    processed_at = fields.DateTime(dump_only=True, format="iso", allow_none=True)


class PaymentCreateSchema(Schema):
    """Payload para registrar un pago manual."""

    amount = fields.Float(required=True, validate=validate.Range(min=0.01))
    method = fields.Enum(PaymentMethod, by_value=True, load_default=PaymentMethod.MANUAL)
    transaction_id = fields.Str(load_default=None, validate=validate.Length(max=200))


class WebhookStripeSchema(Schema):
    """Payload del webhook de Stripe (simplificado)."""

    type = fields.Str(required=True)
    data = fields.Dict(required=True)
