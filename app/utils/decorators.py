"""Decoradores de seguridad y control de acceso (RBAC).

Provee:
    - current_user(): helper para obtener el usuario autenticado desde
      cualquier parte del codigo.
    - @login_required: exige un JWT valido e inyecta el usuario en g.
    - @roles_required(*roles): exige ademas que el rol del usuario este
      entre los permitidos.
    - @medico_or_admin: atajo de roles_required para el modulo clinico.
    - @receptionist_or_above: atajo para agendamiento.
    - @admin_only: atajo para administracion.

Los tokens JWT viajan en HttpOnly cookies (configuradas en config.py).
Para endpoints sensibles se valida el CSRF double-submit cuando proceda.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Iterable

from flask import g, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.exceptions import AuthorizationError, AuthenticationError
from app.models import User, UserRole


def current_user() -> User | None:
    """Retorna el usuario autenticado desde el JWT del request actual.

    Lee el identity del JWT y carga el usuario desde la BD en cada llamada
    (sin cache en g) para garantizar que el clinic_id este siempre actualizado
    y evitar cross-tenant en escenarios de testing con contextos compartidos.

    Returns:
        Instancia de User o None si no hay sesion valida.
    """
    identity: Any = get_jwt_identity()
    if identity is None:
        return None

    try:
        user_id: int = int(identity)
    except (TypeError, ValueError):
        return None

    user: User | None = User.get_by_id(user_id)
    if user is not None:
        g.current_user = user
    return user


def login_required(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorador que exige un JWT valido.

    Inyecta el usuario autenticado en `g.current_user` para que los
    endpoints y servicios lo reutilicen sin volver a consultar la BD.

    Raises:
        AuthenticationError: Si el token falta o el usuario no existe
            o esta inactivo.
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        verify_jwt_in_request()
        user: User | None = current_user()
        if user is None:
            raise AuthenticationError("Usuario no encontrado para el token.")
        if not user.is_active:
            raise AuthenticationError("La cuenta esta desactivada.")
        g.current_user = user
        g.clinic_id = user.clinic_id
        return fn(*args, **kwargs)

    return wrapper


def _normalize_roles(roles: Iterable[UserRole | str]) -> set[str]:
    """Convierte una lista mixta de roles en un conjunto de strings."""
    result: set[str] = set()
    for r in roles:
        if isinstance(r, UserRole):
            result.add(r.value)
        else:
            result.add(str(r).lower())
    return result


def roles_required(
    *roles: UserRole | str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorador que restringe el acceso a los roles indicados.

    Encadena automaticamente la verificacion de sesion (login_required),
    por lo que no es necesario combinar decoradores.

    Args:
        *roles: Uno o mas roles permitidos (ej: UserRole.MEDICO, "admin").

    Raises:
        AuthorizationError: Si el rol del usuario no esta permitido.
    """
    allowed: set[str] = _normalize_roles(roles)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Verifica sesion
            verify_jwt_in_request()
            user: User | None = current_user()
            if user is None:
                raise AuthenticationError("Usuario no encontrado para el token.")
            if not user.is_active:
                raise AuthenticationError("La cuenta esta desactivada.")
            g.current_user = user
            # Multi-tenancy: inyectar clinic_id
            g.clinic_id = user.clinic_id

            if user.role.value not in allowed:
                raise AuthorizationError(
                    message=(
                        f"Tu rol '{user.role.value}' no tiene permiso para "
                        f"esta accion. Roles permitidos: {sorted(allowed)}."
                    ),
                    payload={
                        "required_roles": sorted(allowed),
                        "user_role": user.role.value,
                    },
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# Atajos semanticos por modulo
# ============================================================

def admin_only(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Restringe el endpoint exclusivamente a administradores."""
    return roles_required(UserRole.ADMIN)(fn)


def medico_or_admin(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Restringe el endpoint a medicos y administradores."""
    return roles_required(UserRole.MEDICO, UserRole.ADMIN)(fn)


def receptionist_or_above(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Restringe el endpoint a recepcionistas, medicos y administradores."""
    return roles_required(UserRole.RECEPCIONISTA, UserRole.MEDICO, UserRole.ADMIN)(fn)


def patient_or_above(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Permite acceso a cualquier usuario autenticado (paciente incluido)."""
    return roles_required(
        UserRole.PACIENTE, UserRole.RECEPCIONISTA, UserRole.MEDICO, UserRole.ADMIN
    )(fn)


def super_admin_only(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Restringe el endpoint al super-admin (admin sin clinica).

    El super-admin gestiona la plataforma completa: crea clinicas,
    asigna planes, suspende clinicas, etc.
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        verify_jwt_in_request()
        user: User | None = current_user()
        if user is None:
            raise AuthenticationError("Usuario no encontrado para el token.")
        if not user.is_active:
            raise AuthenticationError("La cuenta esta desactivada.")
        g.current_user = user
        g.clinic_id = user.clinic_id

        if not user.is_super_admin:
            raise AuthorizationError(
                "Esta accion requiere permisos de super-administrador de plataforma."
            )
        return fn(*args, **kwargs)

    return wrapper
