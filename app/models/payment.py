"""Modelo Payment: registro de un pago sobre una factura.

Un pago puede ser via pasarela (Stripe/Conekta) o manual.
Una factura puede tener multiples pagos (parciales, reembolsos).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.exceptions import ValidationError
from app.extensions import db
from .base import BaseModel
from .billing_enums import PaymentMethod, BillingPaymentStatus


class Payment(BaseModel):
    """Registro de pago sobre una factura.

    Attributes:
        invoice_id: FK a la factura.
        amount: Monto del pago.
        currency: Moneda.
        method: Metodo de pago (stripe, conekta, transferencia, etc.).
        status: Estado del pago.
        transaction_id: ID de la transaccion en la pasarela.
        gateway_response: Respuesta cruda de la pasarela (JSON string).
        processed_at: Fecha de procesamiento.
    """

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_invoice", "invoice_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_transaction", "transaction_id"),
    )

    # --- Relacion con factura ---
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )

    # --- Monto ---
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="MXN", nullable=False)

    # --- Metodo y estado ---
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"),
        nullable=False,
        default=PaymentMethod.MANUAL,
    )
    status: Mapped[BillingPaymentStatus] = mapped_column(
        Enum(BillingPaymentStatus, name="payment_status"),
        nullable=False,
        default=BillingPaymentStatus.PENDIENTE,
    )

    # --- Pasarela ---
    transaction_id: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, index=True
    )
    gateway_response: Mapped[Optional[str]] = mapped_column(
        String(2000), nullable=True
    )

    # --- Fechas ---
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # --- Relaciones ---
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} amount={self.amount} "
            f"method={self.method.value} status={self.status.value}>"
        )

    # ============================================================
    # Propiedades
    # ============================================================

    @property
    def is_completed(self) -> bool:
        return self.status == BillingPaymentStatus.COMPLETADO

    # ============================================================
    # Serializacion
    # ============================================================

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = super().to_dict(exclude=exclude)
        data["method"] = self.method.value
        data["status"] = self.status.value
        data["amount"] = float(self.amount)
        if self.processed_at:
            data["processed_at"] = self.processed_at.isoformat()
        return data


# ============================================================
# Validaciones
# ============================================================

@event.listens_for(Payment, "before_insert")
@event.listens_for(Payment, "before_update")
def _validate_payment(mapper, connection, target: Payment) -> None:
    """Valida el pago."""
    if target.amount <= 0:
        raise ValidationError("El monto del pago debe ser positivo.")
    if target.status == BillingPaymentStatus.COMPLETADO and target.processed_at is None:
        target.processed_at = datetime.now(timezone.utc)
