"""Blueprint de autenticacion.

Endpoints:
    POST /api/auth/register   - Registro (paciente auto / admin crea staff)
    POST /api/auth/login      - Inicio de sesion (setea cookies JWT)
    POST /api/auth/logout     - Cierre de sesion (limpia cookies)
    POST /api/auth/refresh    - Renueva access token
    GET  /api/auth/me         - Perfil del usuario autenticado
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    get_jwt_identity,
    set_access_cookies,
    set_refresh_cookies,
    verify_jwt_in_request,
)

from app.exceptions import ValidationError
from app.schemas.user_schemas import LoginSchema, RegisterSchema, UserSchema
from app.services.auth_service import AuthService
from app.utils.decorators import current_user, login_required

auth_bp: Blueprint = Blueprint("auth", __name__)

# Instancias de schemas reutilizables
_register_schema = RegisterSchema()
_login_schema = LoginSchema()
_user_schema = UserSchema()


@auth_bp.route("/register", methods=["POST"])
def register():
    """Registra un nuevo usuario.

    Body: RegisterSchema. Si `role != paciente`, requiere que el caller
    sea admin (cabecera Authorization con JWT valido).
    """
    payload: dict[str, Any] = _parse_json(_register_schema)

    # Si el payload indica un rol de staff, exigir admin
    acting = None
    requested_role = payload.get("role", "paciente")
    if requested_role != "paciente":
        try:
            verify_jwt_in_request(optional=True)
            acting = current_user()
        except Exception:
            acting = None

    user = AuthService.register(payload, acting_user=acting)
    return jsonify({
        "message": "Usuario registrado correctamente.",
        "user": _user_schema.dump(user),
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Inicia sesion y setea las cookies HttpOnly con los tokens JWT.

    Cuando JWT_TOKEN_LOCATION incluye 'headers', el access_token tambien
    se retorna en el cuerpo de la respuesta para uso en clientes que no
    soportan cookies (ej: tests, apps moviles).
    """
    payload: dict[str, Any] = _parse_json(_login_schema)
    user = AuthService.authenticate(payload["email"], payload["password"])
    tokens = AuthService.issue_tokens(user)

    from flask import current_app
    token_locations = current_app.config.get("JWT_TOKEN_LOCATION", ["cookies"])
    response_body: dict[str, Any] = {
        "message": "Sesion iniciada.",
        "user": tokens["user"],
    }
    # Incluir tokens en el body si se soporta headers
    if "headers" in token_locations:
        response_body["access_token"] = tokens["access_token"]
        response_body["refresh_token"] = tokens["refresh_token"]

    response = jsonify(response_body)
    # Setear cookies si se soporta cookies
    if "cookies" in token_locations:
        set_access_cookies(response, tokens["access_token"])
        set_refresh_cookies(response, tokens["refresh_token"])
    return response


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Cierra la sesion eliminando las cookies JWT."""
    response = jsonify({"message": "Sesion cerrada."})
    AuthService.revoke_current_tokens(response)
    return response


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """Emite un nuevo access token a partir del refresh cookie."""
    from flask_jwt_extended import verify_refresh_jwt_in_request

    verify_refresh_jwt_in_request()
    access_token: str = AuthService.refresh_access_token()
    response = jsonify({"message": "Token renovado."})
    set_access_cookies(response, access_token)
    return response


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    """Retorna el perfil del usuario autenticado."""
    user = current_user()
    return jsonify({"user": _user_schema.dump(user)})


# ============================================================
# Helpers
# ============================================================

def _parse_json(schema) -> dict[str, Any]:
    """Parsea el body JSON validandolo con el schema indicado.

    Raises:
        ValidationError: Si el body no es JSON o no valida.
    """
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("El cuerpo de la peticion debe ser JSON.")
    result = schema.load(data)
    return result
