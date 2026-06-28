"""Servicio de integracion con Stripe.

Gestiona:
    - Creacion y actualizacion de clientes Stripe.
    - Creacion de sesiones de checkout para suscripciones.
    - Procesamiento de webhooks (invoice.payment_succeeded,
      invoice.payment_failed, customer.subscription.deleted).
    - Portal de cliente para gestionar metodos de pago.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import stripe
from flask import current_app

from app.exceptions import RecordNotFoundError, ValidationError
from app.extensions import db
from app.models import (
    BillingCycle,
    BillingPaymentStatus,
    Clinic,
    ClinicPlan,
    ClinicStatus,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    Subscription,
    SubscriptionStatus,
)
from app.services.subscription_service import SubscriptionService


class StripeService:
    """Operaciones de integracion con Stripe."""

    # ============================================================
    # Configuracion
    # ============================================================

    @staticmethod
    def _configure() -> None:
        """Configura la API key de Stripe desde la configuracion de Flask."""
        secret_key: str = current_app.config.get("STRIPE_SECRET_KEY", "")
        if not secret_key:
            raise ValidationError("STRIPE_SECRET_KEY no esta configurada.")
        stripe.api_key = secret_key

    @staticmethod
    def _price_id(plan: ClinicPlan, billing_cycle: BillingCycle) -> str:
        """Retorna el Stripe Price ID segun plan y ciclo."""
        mapping: dict[str, dict[str, str]] = {
            "starter": {
                "mensual": current_app.config.get("STRIPE_PRICE_STARTER_MONTHLY", ""),
                "anual": current_app.config.get("STRIPE_PRICE_STARTER_YEARLY", ""),
            },
            "professional": {
                "mensual": current_app.config.get(
                    "STRIPE_PRICE_PROFESSIONAL_MONTHLY", ""
                ),
                "anual": current_app.config.get(
                    "STRIPE_PRICE_PROFESSIONAL_YEARLY", ""
                ),
            },
            "clinic": {
                "mensual": current_app.config.get("STRIPE_PRICE_CLINIC_MONTHLY", ""),
                "anual": current_app.config.get("STRIPE_PRICE_CLINIC_YEARLY", ""),
            },
        }
        price_id: str = mapping.get(plan.value, {}).get(billing_cycle.value, "")
        if not price_id:
            raise ValidationError(
                f"No hay Stripe Price ID configurado para {plan.value}/{billing_cycle.value}."
            )
        return price_id

    @staticmethod
    def _cycle_to_stripe(billing_cycle: BillingCycle) -> str:
        """Mapea el ciclo de cobro interno al formato de Stripe."""
        mapping: dict[BillingCycle, str] = {
            BillingCycle.MENSUAL: "month",
            BillingCycle.TRIMESTRAL: "year",  # Stripe no soporta trimestral nativo
            BillingCycle.ANUAL: "year",
        }
        return mapping.get(billing_cycle, "month")

    # ============================================================
    # Clientes
    # ============================================================

    @staticmethod
    def get_or_create_customer(clinic: Clinic, email: str, name: str) -> str:
        """Obtiene o crea un customer en Stripe para la clinica.

        Returns:
            El Stripe Customer ID.
        """
        StripeService._configure()

        if clinic.stripe_customer_id:
            try:
                customer = stripe.Customer.retrieve(clinic.stripe_customer_id)
                if customer and not customer.get("deleted", False):
                    return clinic.stripe_customer_id
            except stripe.error.InvalidRequestError:
                pass  # Customer no existe, crear nuevo

        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={"clinic_id": clinic.id, "subdomain": clinic.subdomain},
        )
        clinic.stripe_customer_id = customer.id
        db.session.commit()
        return customer.id

    # ============================================================
    # Checkout Session
    # ============================================================

    @staticmethod
    def create_checkout_session(
        clinic: Clinic,
        email: str,
        name: str,
        plan: ClinicPlan,
        billing_cycle: BillingCycle,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        """Crea una sesion de checkout de Stripe para suscribirse.

        Returns:
            Dict con session_id y checkout_url.
        """
        StripeService._configure()

        price_id: str = StripeService._price_id(plan, billing_cycle)
        customer_id: str = StripeService.get_or_create_customer(clinic, email, name)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                "metadata": {
                    "clinic_id": clinic.id,
                    "plan": plan.value,
                    "billing_cycle": billing_cycle.value,
                }
            },
            metadata={
                "clinic_id": clinic.id,
                "plan": plan.value,
                "billing_cycle": billing_cycle.value,
            },
        )

        return {
            "session_id": session.id,
            "checkout_url": session.url,
            "customer_id": customer_id,
        }

    # ============================================================
    # Customer Portal
    # ============================================================

    @staticmethod
    def create_customer_portal_session(
        clinic: Clinic,
        return_url: str,
    ) -> dict[str, Any]:
        """Crea una sesion del portal de cliente de Stripe.

        Returns:
            Dict con portal_url.
        """
        StripeService._configure()

        if not clinic.stripe_customer_id:
            raise ValidationError("La clinica no tiene un customer de Stripe.")

        session = stripe.billing_portal.Session.create(
            customer=clinic.stripe_customer_id,
            return_url=return_url,
        )
        return {"portal_url": session.url}

    # ============================================================
    # Webhooks
    # ============================================================

    @staticmethod
    def construct_event(payload: bytes, sig_header: str | None) -> dict[str, Any]:
        """Construye y verifica un evento de Stripe."""
        StripeService._configure()

        webhook_secret: str = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")
        if not webhook_secret or not sig_header:
            raise ValidationError("Webhook secret o firma no configurados.")

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=webhook_secret,
            )
        except ValueError as exc:
            raise ValidationError("Payload invalido.") from exc
        except stripe.error.SignatureVerificationError as exc:
            raise ValidationError("Firma del webhook invalida.") from exc

        return event

    @staticmethod
    def handle_checkout_session_completed(session: dict[str, Any]) -> dict[str, Any]:
        """Procesa checkout.session.completed."""
        metadata: dict[str, Any] = session.get("metadata", {})
        clinic_id: int | None = _int_metadata(metadata.get("clinic_id"))
        if clinic_id is None:
            raise ValidationError("Metadata clinic_id no encontrada.")

        clinic: Clinic = Clinic.get_or_404(clinic_id)
        subscription_id: str | None = session.get("subscription")
        if not subscription_id:
            raise ValidationError("No se encontro subscription en la sesion.")

        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        plan_value: str = metadata.get("plan", "starter")
        cycle_value: str = metadata.get("billing_cycle", "mensual")

        # Buscar o crear suscripcion interna
        sub: Subscription | None = db.session.scalar(
            db.select(Subscription).where(Subscription.clinic_id == clinic_id)
        )
        if sub is None:
            sub = SubscriptionService.create_subscription(
                clinic_id=clinic_id,
                plan=ClinicPlan[plan_value.upper()],
                billing_cycle=BillingCycle[cycle_value.upper()],
                auto_renew=True,
            )

        sub.stripe_subscription_id = subscription_id
        sub.stripe_price_id = stripe_sub["items"]["data"][0]["price"]["id"]
        sub.status = SubscriptionStatus.ACTIVA
        sub.current_period_start = datetime.fromtimestamp(
            stripe_sub["current_period_start"], tz=timezone.utc
        )
        sub.current_period_end = datetime.fromtimestamp(
            stripe_sub["current_period_end"], tz=timezone.utc
        )

        clinic.status = ClinicStatus.ACTIVA
        clinic.is_active = True
        db.session.commit()

        return {"message": "Suscripcion activada via Stripe.", "subscription_id": sub.id}

    @staticmethod
    def handle_invoice_payment_succeeded(invoice: dict[str, Any]) -> dict[str, Any]:
        """Procesa invoice.payment_succeeded."""
        StripeService._configure()

        subscription_id: str | None = invoice.get("subscription")
        if not subscription_id:
            return {"message": "Invoice sin subscription, ignorado."}

        sub: Subscription | None = db.session.scalar(
            db.select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
        )
        if sub is None:
            return {"message": "Suscripcion no encontrada, ignorado."}

        # Registrar pago si hay un charge asociado
        charge_id: str | None = invoice.get("charge")
        amount_paid: int = invoice.get("amount_paid", 0)
        currency: str = invoice.get("currency", "mxn").upper()

        if charge_id and amount_paid > 0:
            existing: Payment | None = db.session.scalar(
                db.select(Payment).where(Payment.transaction_id == charge_id)
            )
            if existing is None:
                # Buscar factura interna por numero (si existe)
                invoice_number: str | None = invoice.get("number")
                internal_invoice: Invoice | None = None
                if invoice_number:
                    internal_invoice = Invoice.query.filter_by(
                        number=invoice_number
                    ).first()

                # Si no hay factura interna, generar una
                if internal_invoice is None:
                    internal_invoice = SubscriptionService.generate_invoice(sub.id)
                    internal_invoice.number = invoice_number or f"STRIPE-{charge_id}"
                    db.session.commit()

                payment = Payment(
                    invoice_id=internal_invoice.id,
                    amount=amount_paid / 100,
                    currency=currency,
                    method=PaymentMethod.STRIPE,
                    status=BillingPaymentStatus.COMPLETADO,
                    transaction_id=charge_id,
                    gateway_response=str(invoice),
                    processed_at=datetime.now(timezone.utc),
                )
                payment.save()

                if internal_invoice.balance_due <= 0:
                    internal_invoice.status = InvoiceStatus.PAGADA
                    internal_invoice.paid_date = datetime.now(timezone.utc)
                    db.session.commit()

        # Actualizar periodo
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        sub.current_period_start = datetime.fromtimestamp(
            stripe_sub["current_period_start"], tz=timezone.utc
        )
        sub.current_period_end = datetime.fromtimestamp(
            stripe_sub["current_period_end"], tz=timezone.utc
        )
        sub.status = SubscriptionStatus.ACTIVA
        clinic: Clinic = Clinic.get_or_404(sub.clinic_id)
        clinic.status = ClinicStatus.ACTIVA
        clinic.is_active = True
        db.session.commit()

        return {"message": "Pago procesado correctamente."}

    @staticmethod
    def handle_invoice_payment_failed(invoice: dict[str, Any]) -> dict[str, Any]:
        """Procesa invoice.payment_failed."""
        subscription_id: str | None = invoice.get("subscription")
        if not subscription_id:
            return {"message": "Invoice sin subscription, ignorado."}

        sub: Subscription | None = db.session.scalar(
            db.select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
        )
        if sub is None:
            return {"message": "Suscripcion no encontrada, ignorado."}

        # Marcar como pendiente de pago, no suspender inmediatamente
        sub.status = SubscriptionStatus.PENDIENTE_PAGO
        db.session.commit()

        return {"message": "Pago fallido registrado."}

    @staticmethod
    def handle_subscription_deleted(stripe_subscription: dict[str, Any]) -> dict[str, Any]:
        """Procesa customer.subscription.deleted."""
        subscription_id: str | None = stripe_subscription.get("id")
        if not subscription_id:
            return {"message": "Subscription ID no encontrado."}

        sub: Subscription | None = db.session.scalar(
            db.select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
        )
        if sub is None:
            return {"message": "Suscripcion no encontrada, ignorado."}

        SubscriptionService.cancel_subscription(sub.id)
        return {"message": "Suscripcion cancelada via Stripe."}


# ============================================================
# Helpers
# ============================================================

def _int_metadata(value: Any) -> int | None:
    """Convierte metadata de string a int de forma segura."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
