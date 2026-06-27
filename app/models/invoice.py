"""Modelo Invoice: factura generada por cada ciclo de cobro.

Cada suscripcion genera facturas automaticas. La factura puede pagarse
via pasarela (Stripe/Conekta) o manualmente. Una factura pagada activa
el periodo de la suscripcion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.exceptions import ValidationError
from app.extensions import db
from .base import BaseModel
from .billing_enums import InvoiceStatus, PaymentMethod


class Invoice(BaseModel):
    """Factura de cobro de suscripcion.

    Attributes:
        subscription_id: FK a la suscripcion.
        clinic_id: FK a la clinica (denormalizado para queries).
        number: Numero de factura unico (ej: INV-2026-0001).
        status: Estado de la factura.
        amount: Monto a pagar.
        currency: Moneda (MXN, USD).
        period_start: Inicio del periodo que cubre.
        period_end: Fin del periodo que cubre.
        issue_date: Fecha de emision.
        due_date: Fecha de vencimiento del pago.
        paid_date: Fecha de pago (si aplica).
        notes: Notas internas.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_subscription", "subscription_id"),
        Index("ix_invoices_clinic", "clinic_id"),
        Index("ix_invoices_number", "number", unique=True),
        Index("ix_invoices_status", "status"),
    )

    # --- Relaciones ---
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    clinic_id: Mapped[int] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )

    # --- Identificacion ---
    number: Mapped[str] = mapped_column(
        String(30), nullable=False, unique=True, default=lambda: _generate_invoice_number()
    )

    # --- Monto ---
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="MXN", nullable=False)

    # --- Estado ---
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"),
        nullable=False,
        default=InvoiceStatus.EMITIDA,
    )

    # --- Fechas ---
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    issue_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    paid_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # --- Notas ---
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Relaciones ---
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="invoices")
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="invoice", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Invoice {self.number} amount={self.amount} status={self.status.value}>"

    # ============================================================
    # Propiedades
    # ============================================================

    @property
    def is_paid(self) -> bool:
        return self.status == InvoiceStatus.PAGADA

    @property
    def is_overdue(self) -> bool:
        """Indica si la factura esta vencida (no pagada y paso la due_date)."""
        if self.status == InvoiceStatus.PAGADA:
            return False
        due = self.due_date
        now = datetime.now(timezone.utc)
        if due.tzinfo is None:
            now = now.replace(tzinfo=None)
        return now > due

    @property
    def total_paid(self) -> float:
        """Suma de pagos completados."""
        from .payment import Payment, BillingPaymentStatus
        total: float = 0.0
        for p in self.payments:
            if p.status == BillingPaymentStatus.COMPLETADO:
                total += float(p.amount)
        return total

    @property
    def balance_due(self) -> float:
        """Saldo pendiente."""
        return float(self.amount) - self.total_paid

    # ============================================================
    # Serializacion
    # ============================================================

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = super().to_dict(exclude=exclude)
        data["status"] = self.status.value
        data["is_paid"] = self.is_paid
        data["is_overdue"] = self.is_overdue
        data["total_paid"] = self.total_paid
        data["balance_due"] = self.balance_due
        data["amount"] = float(self.amount)
        if self.paid_date:
            data["paid_date"] = self.paid_date.isoformat()
        return data

    # ============================================================
    # Consultas
    # ============================================================

    @classmethod
    def get_by_number(cls, number: str) -> "Invoice":
        from app.exceptions import RecordNotFoundError
        inv: Optional[Invoice] = db.session.scalar(
            db.select(cls).where(cls.number == number)
        )
        if inv is None:
            raise RecordNotFoundError(f"Factura {number!r} no encontrada.")
        return inv

    @classmethod
    def get_by_number_or_404(cls, number: str) -> "Invoice":
        """Alias de get_by_number."""
        return cls.get_by_number(number)


# ============================================================
# Helpers
# ============================================================

def _generate_invoice_number() -> str:
    """Genera un numero de factura unico."""
    import uuid
    year: int = datetime.now(timezone.utc).year
    short: str = uuid.uuid4().hex[:8].upper()
    return f"INV-{year}-{short}"


# ============================================================
# Validaciones
# ============================================================

@event.listens_for(Invoice, "before_insert")
@event.listens_for(Invoice, "before_update")
def _validate_invoice(mapper, connection, target: Invoice) -> None:
    """Valida coherencia de la factura."""
    if target.amount < 0:
        raise ValidationError("El monto de la factura no puede ser negativo.")
    # Normalizar fechas para comparacion (ignorar tz para SQLite)
    ps = target.period_start.replace(tzinfo=None) if target.period_start else None
    pe = target.period_end.replace(tzinfo=None) if target.period_end else None
    if ps and pe and ps >= pe:
        raise ValidationError("El inicio del periodo debe ser anterior al fin.")
