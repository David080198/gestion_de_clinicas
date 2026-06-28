"""Enumeraciones del dominio medico.

Centralizar los tipos enumerados evita "magic strings" dispersos en el
codigo y permite que SQLAlchemy use tipos nativos de PostgreSQL (ENUM)
cuando corresponda.
"""

from __future__ import annotations

import enum


class UserRole(enum.Enum):
    """Roles disponibles en el sistema (RBAC)."""
    ADMIN = "admin"
    MEDICO = "medico"
    RECEPCIONISTA = "recepcionista"
    PACIENTE = "paciente"
    CLINICA = "clinica"


class Gender(enum.Enum):
    """Sexo biologico del paciente para fines clinicos."""
    MASCULINO = "masculino"
    FEMENINO = "femenino"
    OTRO = "otro"
    NO_ESPECIFICADO = "no_especificado"


class BloodType(enum.Enum):
    """Tipo de sangre del paciente."""
    O_POS = "O+"
    O_NEG = "O-"
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    DESCONOCIDO = "desconocido"


class AppointmentStatus(enum.Enum):
    """Estados por los que puede transitar una cita medica.

    Flujo permitido:
        PENDIENTE -> CONFIRMADA -> EN_CONSULTA -> COMPLETADA
        Cualquier estado -> CANCELADA (con restricciones)
    """
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    EN_CONSULTA = "en_consulta"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"


class Weekday(enum.Enum):
    """Dias de la semana para la configuracion de horarios."""
    LUNES = 0
    MARTES = 1
    MIERCOLES = 2
    JUEVES = 3
    VIERNES = 4
    SABADO = 5
    DOMINGO = 6


class PaymentStatus(enum.Enum):
    """Estado del cobro asociado a una cita."""
    PENDIENTE = "pendiente"
    PAGADO = "pagado"
    REEMBOLSADO = "reembolsado"
    CANCELADO = "cancelado"


# Transiciones de estado validas para una cita.
VALID_APPOINTMENT_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.PENDIENTE: {
        AppointmentStatus.CONFIRMADA,
        AppointmentStatus.CANCELADA,
    },
    AppointmentStatus.CONFIRMADA: {
        AppointmentStatus.EN_CONSULTA,
        AppointmentStatus.COMPLETADA,
        AppointmentStatus.CANCELADA,
    },
    AppointmentStatus.EN_CONSULTA: {
        AppointmentStatus.COMPLETADA,
    },
    AppointmentStatus.COMPLETADA: set(),
    AppointmentStatus.CANCELADA: set(),
}
