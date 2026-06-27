"""Utilidades de multi-tenancy: gestion del tenant (clinica) activo.

Proporciona:
    - current_clinic_id(): obtiene el clinic_id del usuario autenticado.
    - current_clinic(): obtiene la instancia de Clinic del usuario.
    - tenant_filter(model): retorna una query filtrada por clinic_id.
    - tenant_query(model): alias de tenant_filter para usar en servicios.
    - resolve_clinic_from_subdomain(): resuelve la clinica por subdominio.

El clinic_id se inyecta en flask.g por los decoradores de autenticacion
para que todos los servicios lo reutilicen sin volver a consultar la BD.
"""

from __future__ import annotations

from typing import Any, Optional

from flask import g, request
from sqlalchemy import select

from app.exceptions import AuthorizationError, RecordNotFoundError, ValidationError
from app.extensions import db
from app.models import Clinic, ClinicStatus, User


# ============================================================
# Resolucion del tenant activo
# ============================================================

def current_clinic_id() -> Optional[int]:
    """Retorna el clinic_id del usuario autenticado.

    Returns:
        int con el clinic_id, o None si es super-admin (gestiona todas).
    """
    # Prioridad 1: cacheado en g por el decorador
    cached: Optional[int] = getattr(g, "clinic_id", None)
    if cached is not None:
        return cached

    # Prioridad 2: derivado del usuario autenticado
    user: Optional[User] = getattr(g, "current_user", None)
    if user is not None:
        g.clinic_id = user.clinic_id
        return user.clinic_id

    return None


def current_clinic() -> Optional[Clinic]:
    """Retorna la instancia de Clinic del usuario autenticado."""
    clinic_id: Optional[int] = current_clinic_id()
    if clinic_id is None:
        return None
    cached: Optional[Clinic] = getattr(g, "clinic", None)
    if cached is not None:
        return cached
    clinic: Optional[Clinic] = db.session.get(Clinic, clinic_id)
    if clinic is not None:
        g.clinic = clinic
    return clinic


def require_clinic_id() -> int:
    """Retorna el clinic_id o lanza error si el usuario no tiene clinica.

    Raises:
        AuthorizationError: Si el usuario no tiene clinica asignada.
    """
    clinic_id: Optional[int] = current_clinic_id()
    if clinic_id is None:
        raise AuthorizationError(
            "Tu cuenta no pertenece a ninguna clinica. "
            "Contacta al administrador de la plataforma."
        )
    return clinic_id


def assert_clinic_operational() -> Clinic:
    """Verifica que la clinica del usuario este operativa.

    Raises:
        AuthorizationError: Si la clinica esta suspendida o cancelada.
    """
    clinic: Optional[Clinic] = current_clinic()
    if clinic is None:
        raise AuthorizationError("No tienes clinica asignada.")
    if not clinic.is_operational:
        raise AuthorizationError(
            f"Tu clinica esta {clinic.status.value}. "
            f"Contacta al administrador para regularizar tu suscripcion."
        )
    return clinic


# ============================================================
# Filtrado automatico de queries
# ============================================================

def tenant_filter(model: type) -> "select":
    """Retorna un select statement filtrado por el clinic_id actual.

    Uso tipico en servicios:
        stmt = tenant_filter(Appointment)
        stmt = stmt.where(Appointment.status == status)
        results = db.session.scalars(stmt).all()

    Si el usuario es super-admin (sin clinic_id), retorna la query sin
    filtrar para que pueda ver todas las clinicas.

    Args:
        model: Clase del modelo que tiene clinic_id.

    Returns:
        select statement filtrado por clinic_id.
    """
    clinic_id: Optional[int] = current_clinic_id()
    stmt = select(model)
    if clinic_id is not None:
        # Solo filtrar si el modelo tiene el atributo clinic_id
        if hasattr(model, "clinic_id"):
            stmt = stmt.where(model.clinic_id == clinic_id)
    return stmt


def tenant_query(model: type) -> "select":
    """Alias de tenant_filter."""
    return tenant_filter(model)


# ============================================================
# Resolucion por subdominio (para landing pages y registro)
# ============================================================

def resolve_clinic_from_request() -> Optional[Clinic]:
    """Resuelve la clinica a partir del Host header de la peticion.

    Ejemplo:
        Host: clinica1.medcenter.app -> subdomain "clinica1"
        Host: medcenter.app          -> None (plataforma global)

    Returns:
        Instancia de Clinic o None si es el dominio principal.
    """
    host: Optional[str] = request.host.split(":")[0] if request else None
    if not host:
        return None

    # Extraer el subdominio (primera parte antes del primer punto)
    # Asumiendo formato: subdominio.dominio.tld
    parts: list[str] = host.split(".")
    if len(parts) < 3:
        # No hay subdominio (ej: medcenter.app, localhost)
        return None

    subdomain: str = parts[0].lower()
    # Ignorar www
    if subdomain == "www":
        return None

    return Clinic.find_by_subdomain(subdomain)


# ============================================================
# Validacion de pertenencia (anti-cross-tenant)
# ============================================================

def assert_resource_belongs_to_clinic(resource: Any, resource_name: str = "recurso") -> None:
    """Verifica que un recurso pertenezca a la clinica del usuario actual.

    Uso tipico:
        apt = Appointment.query.get(id)
        assert_resource_belongs_to_clinic(apt, "cita")

    Raises:
        AuthorizationError: Si el recurso no pertenece a la clinica.
        RecordNotFoundError: Si el recurso es None.
    """
    if resource is None:
        raise RecordNotFoundError(f"{resource_name.capitalize()} no encontrado.")

    # Super-admin puede ver todo
    clinic_id: Optional[int] = current_clinic_id()
    if clinic_id is None:
        return

    # Si el recurso tiene clinic_id, validar pertenencia
    resource_clinic_id: Optional[int] = getattr(resource, "clinic_id", None)
    if resource_clinic_id is not None and resource_clinic_id != clinic_id:
        raise AuthorizationError(
            f"No tienes acceso a este {resource_name}. "
            f"Pertenece a otra clinica."
        )
