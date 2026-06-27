"""Servicio de suscripciones y facturacion.

Gestiona el ciclo de vida completo:
    - Crear suscripcion (con periodo de prueba).
    - Generar facturas automaticas al inicio de cada ciclo.
    - Registrar pagos (manuales o via pasarela).
    - Activar/suspender suscripcion segun estado de pago.
    - Renovar automaticamente (si auto_renew=True y hay pago).
    - Cancelar suscripcion.
    - Verificar acceso (middleware de suscripcion).

La integracion con Stripe/Conekta se prepara via webhooks; el servicio
recibe la confirmacion de pago y actualiza el estado internamente.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select

from app.exceptions import (
    AuthorizationError,
    DuplicateResourceError,
    RecordNotFoundError,
    ValidationError,
)
from app.extensions import db
from app.models import (
    BillingCycle,
    Clinic,
    ClinicPlan,
    ClinicStatus,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    BillingPaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.models.billing_enums import PLAN_PRICING, TRIAL_PERIOD_DAYS

UTC = timezone.utc


class SubscriptionService:
    """Operaciones de gestion de suscripciones."""

    # ============================================================
    # Creacion de suscripcion
    # ============================================================

    @staticmethod
    def create_subscription(
        clinic_id: int,
        plan: ClinicPlan = ClinicPlan.STARTER,
        billing_cycle: BillingCycle = BillingCycle.MENSUAL,
        auto_renew: bool = True,
        price_override: float | None = None,
    ) -> Subscription:
        """Crea una suscripcion para una clinica con periodo de prueba.

        Raises:
            DuplicateResourceError: Si la clinica ya tiene suscripcion.
            RecordNotFoundError: Si la clinica no existe.
        """
        clinic: Clinic = Clinic.get_or_404(clinic_id)

        # Verificar que no tenga suscripcion activa previa
        existing: Subscription | None = db.session.scalar(
            select(Subscription).where(Subscription.clinic_id == clinic_id)
        )
        if existing is not None and existing.status != SubscriptionStatus.CANCELADA:
            raise DuplicateResourceError(
                f"La clinica {clinic.name} ya tiene una suscripcion activa."
            )
        # Si existe pero esta cancelada, reactivar creando una nueva
        if existing is not None and existing.status == SubscriptionStatus.CANCELADA:
            # Eliminar la suscripcion cancelada para crear una nueva
            db.session.delete(existing)
            db.session.flush()

        now: datetime = datetime.now(UTC)
        trial_end: datetime = now + timedelta(days=TRIAL_PERIOD_DAYS)

        sub = Subscription(
            clinic_id=clinic_id,
            plan=plan,
            billing_cycle=billing_cycle,
            status=SubscriptionStatus.PRUEBA,
            started_at=now,
            trial_ends_at=trial_end,
            auto_renew=auto_renew,
            price_override=price_override,
        )
        sub.save()

        # Sincronizar plan y estado de la clinica
        clinic.plan = plan
        clinic.status = ClinicStatus.PRUEBA
        db.session.commit()

        return sub

    # ============================================================
    # Consulta
    # ============================================================

    @staticmethod
    def get_by_clinic(clinic_id: int) -> Subscription:
        """Recupera la suscripcion de una clinica.

        Raises:
            RecordNotFoundError: Si la clinica no tiene suscripcion.
        """
        sub: Subscription | None = db.session.scalar(
            select(Subscription).where(Subscription.clinic_id == clinic_id)
        )
        if sub is None:
            raise RecordNotFoundError(
                f"La clinica {clinic_id} no tiene suscripcion activa."
            )
        return sub

    @staticmethod
    def get_or_404(subscription_id: int) -> Subscription:
        sub: Subscription | None = db.session.get(Subscription, subscription_id)
        if sub is None:
            raise RecordNotFoundError(f"Suscripcion {subscription_id} no encontrada.")
        return sub

    # ============================================================
    # Verificacion de acceso (middleware)
    # ============================================================

    @staticmethod
    def check_clinic_access(clinic_id: int) -> Subscription:
        """Verifica que la clinica tenga acceso activo.

        Raises:
            AuthorizationError: Si la suscripcion esta vencida/suspendida.
            RecordNotFoundError: Si no tiene suscripcion.
        """
        sub: Subscription = SubscriptionService.get_by_clinic(clinic_id)

        # Si esta en prueba y el trial expiro, suspender
        if sub.is_trial and sub.trial_expired:
            SubscriptionService._suspend_for_nonpayment(sub)
            raise AuthorizationError(
                "Tu periodo de prueba ha terminado. Suscribete para continuar."
            )

        # Si el periodo de cobro expiro y no hay pago, suspender
        if sub.status == SubscriptionStatus.ACTIVA and sub.period_expired:
            if not sub.auto_renew:
                SubscriptionService._mark_expired(sub)
                raise AuthorizationError(
                    "Tu suscripcion ha vencido. Renueva para continuar."
                )
            # Si auto_renew, intentar generar nueva factura
            SubscriptionService.generate_invoice(sub.id)

        if not sub.is_active:
            raise AuthorizationError(
                f"Tu suscripcion esta {sub.status.value}. "
                f"Regulariza tu pago para continuar."
            )

        return sub

    # ============================================================
    # Generacion de facturas
    # ============================================================

    @staticmethod
    def generate_invoice(subscription_id: int) -> Invoice:
        """Genera la factura del siguiente periodo de cobro.

        Raises:
            ValidationError: Si ya existe una factura para el periodo.
        """
        sub: Subscription = SubscriptionService.get_or_404(subscription_id)
        period_start: datetime = sub.next_period_start()
        period_end: datetime = period_start + sub.cycle_duration()

        # Verificar que no exista factura para este periodo
        existing: Invoice | None = db.session.scalar(
            select(Invoice).where(
                Invoice.subscription_id == subscription_id,
                Invoice.period_start == period_start,
            )
        )
        if existing is not None:
            raise ValidationError(
                "Ya existe una factura para este periodo."
            )

        invoice = Invoice(
            subscription_id=subscription_id,
            clinic_id=sub.clinic_id,
            amount=sub.price,
            currency="MXN",
            status=InvoiceStatus.EMITIDA,
            period_start=period_start,
            period_end=period_end,
            issue_date=datetime.now(UTC),
            due_date=datetime.now(UTC) + timedelta(days=7),  # 7 dias para pagar
        )
        invoice.save()
        return invoice

    # ============================================================
    # Registro de pagos
    # ============================================================

    @staticmethod
    def register_payment(
        invoice_id: int,
        amount: float,
        method: PaymentMethod = PaymentMethod.MANUAL,
        transaction_id: str | None = None,
        gateway_response: str | None = None,
    ) -> Payment:
        """Registra un pago sobre una factura.

        Si el pago cubre el saldo, marca la factura como PAGADA y activa
        la suscripcion para el periodo correspondiente.

        Returns:
            El pago registrado.
        """
        invoice: Invoice = Invoice.get_by_number_or_404(invoice_id) if isinstance(invoice_id, str) else db.session.get(Invoice, invoice_id)
        if invoice is None:
            raise RecordNotFoundError(f"Factura {invoice_id} no encontrada.")

        payment = Payment(
            invoice_id=invoice.id,
            amount=amount,
            currency=invoice.currency,
            method=method,
            status=BillingPaymentStatus.COMPLETADO,
            transaction_id=transaction_id,
            gateway_response=gateway_response,
            processed_at=datetime.now(UTC),
        )
        payment.save()

        # Verificar si la factura esta completamente pagada
        if invoice.balance_due <= 0 and invoice.status != InvoiceStatus.PAGADA:
            invoice.status = InvoiceStatus.PAGADA
            invoice.paid_date = datetime.now(UTC)
            db.session.commit()

            # Activar la suscripcion para el periodo de la factura
            SubscriptionService._activate_period(invoice)

        return payment

    @staticmethod
    def _activate_period(invoice: Invoice) -> None:
        """Activa la suscripcion para el periodo cubierto por la factura."""
        sub: Subscription = SubscriptionService.get_or_404(invoice.subscription_id)
        sub.current_period_start = invoice.period_start
        sub.current_period_end = invoice.period_end
        sub.status = SubscriptionStatus.ACTIVA

        # Sincronizar estado de la clinica
        clinic: Clinic = Clinic.get_or_404(sub.clinic_id)
        clinic.status = ClinicStatus.ACTIVA
        clinic.is_active = True

        db.session.commit()

    # ============================================================
    # Suspension y cancelacion
    # ============================================================

    @staticmethod
    def _suspend_for_nonpayment(sub: Subscription) -> None:
        """Suspende la suscripcion por falta de pago."""
        sub.status = SubscriptionStatus.SUSPENDIDA
        clinic: Clinic = Clinic.get_or_404(sub.clinic_id)
        clinic.status = ClinicStatus.SUSPENDIDA
        clinic.is_active = False
        db.session.commit()

    @staticmethod
    def _mark_expired(sub: Subscription) -> None:
        """Marca la suscripcion como vencida."""
        sub.status = SubscriptionStatus.VENCIDA
        clinic: Clinic = Clinic.get_or_404(sub.clinic_id)
        clinic.status = ClinicStatus.SUSPENDIDA
        clinic.is_active = False
        db.session.commit()

    @staticmethod
    def cancel_subscription(subscription_id: int, reason: str | None = None) -> Subscription:
        """Cancela una suscripcion.

        La clinica pierde acceso inmediato. No se eliminan los datos.
        """
        sub: Subscription = SubscriptionService.get_or_404(subscription_id)
        sub.status = SubscriptionStatus.CANCELADA
        sub.cancelled_at = datetime.now(UTC)
        sub.auto_renew = False

        clinic: Clinic = Clinic.get_or_404(sub.clinic_id)
        clinic.status = ClinicStatus.CANCELADA
        clinic.is_active = False

        db.session.commit()
        return sub

    @staticmethod
    def reactivate_subscription(subscription_id: int) -> Subscription:
        """Reactiva una suscripcion suspendida o vencida.

        Genera una nueva factura para el proximo periodo.
        """
        sub: Subscription = SubscriptionService.get_or_404(subscription_id)
        if sub.status == SubscriptionStatus.CANCELADA:
            raise ValidationError(
                "Una suscripcion cancelada no se puede reactivar. Crea una nueva."
            )

        sub.status = SubscriptionStatus.PENDIENTE_PAGO
        db.session.commit()

        # Generar nueva factura
        SubscriptionService.generate_invoice(sub.id)
        return sub

    # ============================================================
    # Cambio de plan
    # ============================================================

    @staticmethod
    def change_plan(subscription_id: int, new_plan: ClinicPlan) -> Subscription:
        """Cambia el plan de una suscripcion.

        Genera una factura prorrateada si es un upgrade.
        """
        sub: Subscription = SubscriptionService.get_or_404(subscription_id)
        old_plan: ClinicPlan = sub.plan
        sub.plan = new_plan

        # Sincronizar plan de la clinica
        clinic: Clinic = Clinic.get_or_404(sub.clinic_id)
        clinic.plan = new_plan

        db.session.commit()

        # Si es upgrade, generar factura prorrateada
        pricing_old: dict = PLAN_PRICING.get(old_plan.value, {})
        pricing_new: dict = PLAN_PRICING.get(new_plan.value, {})
        old_price: float = pricing_old.get(sub.billing_cycle.value, 0)
        new_price: float = pricing_new.get(sub.billing_cycle.value, 0)

        if new_price > old_price:
            # Prorratear la diferencia
            prorated: float = new_price - old_price
            now: datetime = datetime.now(UTC)
            invoice = Invoice(
                subscription_id=sub.id,
                clinic_id=sub.clinic_id,
                amount=prorated,
                currency="MXN",
                status=InvoiceStatus.EMITIDA,
                period_start=now,
                period_end=sub.current_period_end or now + sub.cycle_duration(),
                issue_date=now,
                due_date=now + timedelta(days=7),
                notes=f"Prorrateo upgrade {old_plan.value} -> {new_plan.value}",
            )
            invoice.save()

        return sub

    # ============================================================
    # Cambio de ciclo de cobro
    # ============================================================

    @staticmethod
    def change_billing_cycle(
        subscription_id: int, new_cycle: BillingCycle
    ) -> Subscription:
        """Cambia el ciclo de cobro de una suscripcion."""
        sub: Subscription = SubscriptionService.get_or_404(subscription_id)
        sub.billing_cycle = new_cycle
        db.session.commit()
        return sub

    # ============================================================
    # Listado de facturas
    # ============================================================

    @staticmethod
    def list_invoices(
        subscription_id: int,
        status: InvoiceStatus | None = None,
    ) -> list[Invoice]:
        """Lista las facturas de una suscripcion."""
        stmt = select(Invoice).where(Invoice.subscription_id == subscription_id)
        if status is not None:
            stmt = stmt.where(Invoice.status == status)
        stmt = stmt.order_by(Invoice.issue_date.desc())
        return list(db.session.scalars(stmt))

    @staticmethod
    def list_clinic_invoices(clinic_id: int) -> list[Invoice]:
        """Lista las facturas de una clinica."""
        stmt = (
            select(Invoice)
            .where(Invoice.clinic_id == clinic_id)
            .order_by(Invoice.issue_date.desc())
        )
        return list(db.session.scalars(stmt))

    # ============================================================
    # Stats de facturacion (para super-admin)
    # ============================================================

    @staticmethod
    def get_billing_stats() -> dict[str, Any]:
        """Retorna estadisticas globales de facturacion."""
        from sqlalchemy import func

        total_subscriptions: int = db.session.scalar(
            select(func.count(Subscription.id))
        ) or 0
        active_subscriptions: int = db.session.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVA,
                    SubscriptionStatus.PRUEBA,
                ])
            )
        ) or 0
        trial_subscriptions: int = db.session.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.PRUEBA
            )
        ) or 0
        suspended_subscriptions: int = db.session.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.SUSPENDIDA
            )
        ) or 0

        # Ingresos del mes (facturas pagadas)
        now: datetime = datetime.now(UTC)
        month_start: datetime = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_revenue: float = float(db.session.scalar(
            select(func.sum(Invoice.amount)).where(
                Invoice.status == InvoiceStatus.PAGADA,
                Invoice.paid_date >= month_start,
            )
        ) or 0.0)

        # Facturas pendientes
        pending_invoices: int = db.session.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.status.in_([InvoiceStatus.EMITIDA, InvoiceStatus.VENCIDA])
            )
        ) or 0

        # MRR (Monthly Recurring Revenue) estimado
        mrr: float = 0.0
        active_subs: list[Subscription] = list(
            db.session.scalars(
                select(Subscription).where(
                    Subscription.status == SubscriptionStatus.ACTIVA
                )
            )
        )
        for s in active_subs:
            # Normalizar a mensual
            if s.billing_cycle == BillingCycle.MENSUAL:
                mrr += s.price
            elif s.billing_cycle == BillingCycle.TRIMESTRAL:
                mrr += s.price / 3
            elif s.billing_cycle == BillingCycle.ANUAL:
                mrr += s.price / 12

        return {
            "total_subscriptions": total_subscriptions,
            "active": active_subscriptions,
            "trial": trial_subscriptions,
            "suspended": suspended_subscriptions,
            "monthly_revenue": round(monthly_revenue, 2),
            "pending_invoices": pending_invoices,
            "mrr": round(mrr, 2),
            "currency": "MXN",
        }
