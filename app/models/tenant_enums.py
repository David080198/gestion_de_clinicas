"""Enumeraciones adicionales para multi-tenancy y suscripciones."""

from __future__ import annotations

import enum


class ClinicStatus(enum.Enum):
    """Estado de una clinica en la plataforma."""
    ACTIVA = "activa"
    SUSPENDIDA = "suspendida"
    CANCELADA = "cancelada"
    PRUEBA = "prueba"


class ClinicPlan(enum.Enum):
    """Planes disponibles para una clinica.

    Nota: La logica de billing/cobros se implementa en la Fase 6.
    Por ahora el plan es informativo y controla limites de uso.
    """
    STARTER = "starter"
    PROFESSIONAL = "professional"
    CLINIC = "clinic"
    ENTERPRISE = "enterprise"


# Limites por plan (medicos y pacientes maximos)
PLAN_LIMITS: dict[ClinicPlan, dict[str, int]] = {
    ClinicPlan.STARTER: {"max_doctors": 1, "max_patients": 200},
    ClinicPlan.PROFESSIONAL: {"max_doctors": 5, "max_patients": 1000},
    ClinicPlan.CLINIC: {"max_doctors": 50, "max_patients": 10000},
    ClinicPlan.ENTERPRISE: {"max_doctors": -1, "max_patients": -1},  # ilimitado
}
