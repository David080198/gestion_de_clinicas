"""Enumeraciones de suscripciones y facturacion."""

from __future__ import annotations

import enum


class SubscriptionStatus(enum.Enum):
    """Estado de una suscripcion de clinica."""
    ACTIVA = "activa"
    PRUEBA = "prueba"
    PENDIENTE_PAGO = "pendiente_pago"
    SUSPENDIDA = "suspendida"
    CANCELADA = "cancelada"
    VENCIDA = "vencida"


class BillingCycle(enum.Enum):
    """Ciclo de facturacion."""
    MENSUAL = "mensual"
    TRIMESTRAL = "trimestral"
    ANUAL = "anual"


class InvoiceStatus(enum.Enum):
    """Estado de una factura."""
    BORRADOR = "borrador"
    EMITIDA = "emitida"
    PAGADA = "pagada"
    VENCIDA = "vencida"
    CANCELADA = "cancelada"


class PaymentMethod(enum.Enum):
    """Metodo de pago."""
    STRIPE = "stripe"
    CONEKTA = "conekta"
    MERCADO_PAGO = "mercadopago"
    TRANSFERENCIA = "transferencia"
    EFECTIVO = "efectivo"
    MANUAL = "manual"


class BillingPaymentStatus(enum.Enum):
    """Estado de un pago de suscripcion."""
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    FALLIDO = "fallido"
    REEMBOLSADO = "reembolsado"


# Precios por plan y ciclo (en MXN)
PLAN_PRICING: dict[str, dict[str, float]] = {
    "starter": {
        "mensual": 1500.00,
        "trimestral": 4050.00,   # 10% descuento
        "anual": 14400.00,       # 20% descuento
    },
    "professional": {
        "mensual": 3500.00,
        "trimestral": 9450.00,
        "anual": 33600.00,
    },
    "clinic": {
        "mensual": 7500.00,
        "trimestral": 20250.00,
        "anual": 72000.00,
    },
    "enterprise": {
        "mensual": 0.00,   # precio personalizado
        "trimestral": 0.00,
        "anual": 0.00,
    },
}

# Duracion del periodo de prueba en dias
TRIAL_PERIOD_DAYS: int = 14
