"""Paquete de modelos del dominio medico.

Centralizar las importaciones aqui permite que:
    - El application factory registre todos los modelos en el metadata de
      SQLAlchemy con un solo `from app import models`.
    - Flask-Migrate (Alembic) autodetecte todas las tablas al generar
      migraciones.
    - El resto del codigo importe modelos con rutas estables, ej:
          from app.models import User, Patient, Appointment
"""

from __future__ import annotations

from .base import BaseModel, TimestampMixin
from .enums import (
    AppointmentStatus,
    BloodType,
    Gender,
    PaymentStatus,
    UserRole,
    Weekday,
    VALID_APPOINTMENT_TRANSITIONS,
)
from .tenant_enums import ClinicPlan, ClinicStatus, PLAN_LIMITS
from .billing_enums import (
    BillingCycle,
    BillingPaymentStatus,
    InvoiceStatus,
    PaymentMethod,
    SubscriptionStatus,
    PLAN_PRICING,
    TRIAL_PERIOD_DAYS,
)
from .clinic import Clinic
from .user import User
from .patient import Patient
from .doctor import Doctor
from .doctor_schedule import DoctorSchedule
from .appointment import Appointment
from .medical_record import MedicalRecord
from .prescription import Prescription
from .subscription import Subscription
from .invoice import Invoice
from .payment import Payment

__all__ = [
    # Base
    "BaseModel",
    "TimestampMixin",
    # Enums
    "UserRole",
    "Gender",
    "BloodType",
    "AppointmentStatus",
    "PaymentStatus",
    "Weekday",
    "VALID_APPOINTMENT_TRANSITIONS",
    # Multi-tenancy
    "Clinic",
    "ClinicPlan",
    "ClinicStatus",
    "PLAN_LIMITS",
    # Billing
    "Subscription",
    "Invoice",
    "Payment",
    "BillingCycle",
    "InvoiceStatus",
    "PaymentMethod",
    "BillingPaymentStatus",
    "SubscriptionStatus",
    "PLAN_PRICING",
    "TRIAL_PERIOD_DAYS",
    # Modelos
    "User",
    "Patient",
    "Doctor",
    "DoctorSchedule",
    "Appointment",
    "MedicalRecord",
    "Prescription",
]
