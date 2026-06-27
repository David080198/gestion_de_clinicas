"""Excepciones personalizadas del dominio medico.

Estas excepciones permiten un manejo de errores semantico y centralizado
mediante un manejador de errores registrado en el application factory.
Cada excepcion incluye un codigo HTTP y un mensaje orientado al usuario.
"""

from __future__ import annotations

from typing import Any


class ClinicBaseError(Exception):
    """Clase base para todas las excepciones del dominio clinico.

    Attributes:
        message: Mensaje legible para el usuario final.
        status_code: Codigo HTTP asociado a la respuesta.
        payload: Informacion adicional opcional para el cuerpo del error.
    """

    message: str = "Ocurrio un error inesperado en el sistema."
    status_code: int = 500

    def __init__(
        self,
        message: str | None = None,
        status_code: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message: str = message or self.__class__.message
        self.status_code: int = status_code or self.__class__.status_code
        self.payload: dict[str, Any] = payload or {}

    def to_dict(self) -> dict[str, Any]:
        """Serializa la excepcion a un dict apto para responder como JSON."""
        body: dict[str, Any] = {"error": self.message, "code": self.status_code}
        if self.payload:
            body["details"] = self.payload
        return body


# ============================================================
# Autenticacion y autorizacion
# ============================================================

class AuthenticationError(ClinicBaseError):
    """Credenciales invalidas o token ausente/expirado."""
    message = "Autenticacion requerida o credenciales invalidas."
    status_code = 401


class AuthorizationError(ClinicBaseError):
    """El usuario autenticado no tiene el rol necesario para la accion."""
    message = "No tienes permisos para realizar esta accion."
    status_code = 403


class TokenExpiredError(AuthenticationError):
    """El token JWT ha expirado y debe renovarse."""
    message = "Tu sesion ha expirado. Inicia sesion nuevamente."
    status_code = 401


# ============================================================
# Reglas de negocio - Citas
# ============================================================

class AppointmentCollisionError(ClinicBaseError):
    """Dos citas chocan en el mismo horario para el mismo medico."""
    message = "El horario seleccionado colisiona con otra cita existente."
    status_code = 409


class AppointmentStateError(ClinicBaseError):
    """Transicion de estado de cita no permitida (ej: cancelar una completada)."""
    message = "La transicion de estado solicitada no es valida."
    status_code = 422


class OutOfScheduleError(ClinicBaseError):
    """La cita solicitada esta fuera del horario de atencion del medico."""
    message = "El medico no atiende en el horario seleccionado."
    status_code = 422


# ============================================================
# Reglas de negocio - Expediente clinico
# ============================================================

class MedicalRecordImmutableError(ClinicBaseError):
    """Intento de modificar un expediente clinico ya guardado (auditoria)."""
    message = "El expediente clinico es inmutable y no puede modificarse."
    status_code = 422


class RecordNotFoundError(ClinicBaseError):
    """El recurso solicitado no existe en la base de datos."""
    message = "El recurso solicitado no fue encontrado."
    status_code = 404


class DuplicateResourceError(ClinicBaseError):
    """Intento de crear un recurso que ya existe (ej: email duplicado)."""
    message = "El recurso ya existe."
    status_code = 409


class ValidationError(ClinicBaseError):
    """Validacion de datos de entrada fallida."""
    message = "Los datos proporcionados no son validos."
    status_code = 400
