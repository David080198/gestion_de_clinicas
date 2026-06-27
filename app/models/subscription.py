"""Modelo Subscription: suscripcion de una clinica a un plan.

Gestiona el ciclo de vida de la suscripcion:
    - Periodo de prueba (TRIAL)
    - Activa con pagos recurrentes
    - Suspendida por falta de pago
    - Cancelada por el cliente o el super-admin

Cada suscripcion genera facturas automaticas segun el ciclo de cobro.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Numeric, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.exceptions import ValidationError
from app.extensions import db
from .base import BaseModel
from .billing_enums import BillingCycle, SubscriptionStatus, PLAN_PRICING, TRIAL_PERIOD_DAYS
from .tenant_enums import ClinicPlan


class Subscription(BaseModel):
    """Suscripcion de una clinica a un plan de la plataforma.

    Attributes:
        clinic_id: FK a la clinica suscrita.
        plan: Plan contratado (starter, professional, clinic, enterprise).
        billing_cycle: Ciclo de cobro (mensual, trimestral, anual).
        status: Estado de la suscripcion.
        started_at: Fecha de inicio de la suscripcion.
        trial_ends_at: Fecha de fin del periodo de prueba.
        current_period_start: Inicio del periodo de cobro actual.
        current_period_end: Fin del periodo de cobro actual.
        auto_renew: Renovacion automatica al vencer el periodo.
        cancelled_at: Fecha de cancelacion (si aplica).
        payment_method_id: ID del metodo de pago en la pasarela (opcional).
        price_override: Precio personalizado (para enterprise o descuentos).
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_clinic", "clinic_id"),
        Index("ix_subscriptions_status", "status"),
    )

    # --- Relacion con clinica ---
    clinic_id: Mapped[int] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # --- Plan y ciclo ---
    plan: Mapped[ClinicPlan] = mapped_column(
        Enum(ClinicPlan, name="subscription_plan"),
        nullable=False,
        default=ClinicPlan.STARTER,
    )
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        Enum(BillingCycle, name="billing_cycle"),
        nullable=False,
        default=BillingCycle.MENSUAL,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"),
        nullable=False,
        default=SubscriptionStatus.PRUEBA,
    )

    # --- Fechas del ciclo ---
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # --- Configuracion ---
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    payment_method_id: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
    )
    price_override: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2), nullable=True,
    )

    # --- Relaciones ---
    clinic: Mapped["Clinic"] = relationship("Clinic")
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="subscription", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Subscription clinic={self.clinic_id} plan={self.plan.value} "
            f"status={self.status.value}>"
        )

    # ============================================================
    # Propiedades derivadas
    # ============================================================

    @property
    def price(self) -> float:
        """Precio del periodo actual segun plan y ciclo.

        Si price_override esta seteado, usa ese; si no, usa PLAN_PRICING.
        """
        if self.price_override is not None:
            return float(self.price_override)
        pricing: dict[str, float] | None = PLAN_PRICING.get(self.plan.value)
        if pricing is None:
            return 0.0
        return pricing.get(self.billing_cycle.value, 0.0)

    @property
    def is_active(self) -> bool:
        """Indica si la suscripcion da acceso a la clinica."""
        return self.status in {
            SubscriptionStatus.ACTIVA,
            SubscriptionStatus.PRUEBA,
        }

    @property
    def is_trial(self) -> bool:
        """Indica si esta en periodo de prueba."""
        return self.status == SubscriptionStatus.PRUEBA

    @property
    def trial_expired(self) -> bool:
        """Indica si el periodo de prueba ha vencido."""
        if self.trial_ends_at is None:
            return False
        trial = self.trial_ends_at
        now = datetime.now(timezone.utc)
        # Normalizar tz para comparacion (SQLite guarda naive)
        if trial.tzinfo is None:
            now = now.replace(tzinfo=None)
        return now > trial

    @property
    def period_expired(self) -> bool:
        """Indica si el periodo de cobro actual ha vencido."""
        if self.current_period_end is None:
            return False
        end = self.current_period_end
        now = datetime.now(timezone.utc)
        if end.tzinfo is None:
            now = now.replace(tzinfo=None)
        return now > end

    @property
    def days_until_expiry(self) -> int | None:
        """Dias restantes hasta el vencimiento del periodo."""
        end: datetime | None = self.current_period_end or self.trial_ends_at
        if end is None:
            return None
        now = datetime.now(timezone.utc)
        if end.tzinfo is None:
            now = now.replace(tzinfo=None)
        delta: timedelta = end - now
        return max(0, delta.days)

    # ============================================================
    # Calculo de fechas
    # ============================================================

    def cycle_duration(self) -> timedelta:
        """Retorna la duracion del ciclo de cobro."""
        durations: dict[BillingCycle, timedelta] = {
            BillingCycle.MENSUAL: timedelta(days=30),
            BillingCycle.TRIMESTRAL: timedelta(days=90),
            BillingCycle.ANUAL: timedelta(days=365),
        }
        return durations.get(self.billing_cycle, timedelta(days=30))

    def next_period_start(self) -> datetime:
        """Inicio del siguiente periodo."""
        if self.current_period_end:
            return self.current_period_end
        return datetime.now(timezone.utc)

    def next_period_end(self) -> datetime:
        """Fin del siguiente periodo."""
        return self.next_period_start() + self.cycle_duration()

    # ============================================================
    # Serializacion
    # ============================================================

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = super().to_dict(exclude=exclude)
        data["plan"] = self.plan.value
        data["billing_cycle"] = self.billing_cycle.value
        data["status"] = self.status.value
        data["price"] = self.price
        data["is_active"] = self.is_active
        data["is_trial"] = self.is_trial
        data["trial_expired"] = self.trial_expired
        data["period_expired"] = self.period_expired
        data["days_until_expiry"] = self.days_until_expiry
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.trial_ends_at:
            data["trial_ends_at"] = self.trial_ends_at.isoformat()
        if self.current_period_start:
            data["current_period_start"] = self.current_period_start.isoformat()
        if self.current_period_end:
            data["current_period_end"] = self.current_period_end.isoformat()
        if self.cancelled_at:
            data["cancelled_at"] = self.cancelled_at.isoformat()
        return data


# ============================================================
# Validaciones
# ============================================================

@event.listens_for(Subscription, "before_insert")
@event.listens_for(Subscription, "before_update")
def _validate_subscription(mapper, connection, target: Subscription) -> None:
    """Valida coherencia de la suscripcion."""
    if target.status == SubscriptionStatus.CANCELADA and target.cancelled_at is None:
        target.cancelled_at = datetime.now(timezone.utc)
