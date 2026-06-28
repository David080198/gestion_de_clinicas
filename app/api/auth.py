"""Blueprint de autenticacion.

Endpoints:
    POST /api/auth/register          - Registro (paciente auto / admin crea staff)
    POST /api/auth/register-clinic   - Registro de clinica y su administrador
    POST /api/auth/login             - Inicio de sesion (setea cookies JWT)
    POST /api/auth/logout            - Cierre de sesion (limpia cookies)
    POST /api/auth/refresh           - Renueva access token
    GET  /api/auth/me                - Perfil del usuario autenticado
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
from sqlalchemy import select

from app.exceptions import ValidationError
from app.extensions import db
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


@auth_bp.route("/register-clinic", methods=["POST"])
def register_clinic():
    """Registra una nueva clinica y su administrador.

    Body: Contiene datos de la clinica y del administrador.
    Crea un Clinic record y un User record con role='clinica'.
    """
    from app.models import Clinic, User, UserRole
    import re
    
    payload: dict[str, Any] = request.get_json(silent=True)
    if payload is None:
        raise ValidationError("El cuerpo de la peticion debe ser JSON.")

    try:
        # Validar campos requeridos
        required_fields = [
            "clinic_name", "tax_id", "clinic_phone", "address",
            "city", "state", "email", "password", "first_name", "last_name"
        ]
        for field in required_fields:
            if field not in payload or not payload[field]:
                raise ValidationError(f"El campo '{field}' es requerido.")

        # Generar slug simple sin dependencias externas
        def generate_slug(text: str) -> str:
            """Convierte un texto a slug: lowercase, reemplaza espacios con guiones."""
            slug = text.lower().strip()
            slug = re.sub(r'[^\w\s-]', '', slug)  # Remueve caracteres especiales
            slug = re.sub(r'[-\s]+', '-', slug)  # Reemplaza espacios/guiones multiples
            return slug.strip('-')
        
        base_slug = generate_slug(payload["clinic_name"])
        slug = base_slug
        subdomain = base_slug
        
        # Verificar que no exista otra clinica con el mismo slug/subdomain
        counter = 1
        while Clinic.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            subdomain = f"{base_slug}-{counter}"
            counter += 1

        # Validar unicidad de email
        email_lower = payload["email"].lower().strip()
        email_exists: User | None = db.session.scalar(
            select(User).where(User.email == email_lower)
        )
        if email_exists is not None:
            raise ValidationError(f"El email {email_lower!r} ya esta registrado.")

        # Crear la clinica
        clinic = Clinic(
            name=payload["clinic_name"],
            slug=slug,
            subdomain=subdomain,
            address=payload.get("address"),
            phone=payload.get("clinic_phone"),
            email=payload.get("email"),
            city=payload.get("city"),
            state=payload.get("state"),
            tax_id=payload.get("tax_id"),
        )
        db.session.add(clinic)
        db.session.flush()  # Para obtener el ID sin commitear

        # Crear el usuario administrador directamente
        user = User(
            email=email_lower,
            first_name=payload["first_name"].strip(),
            last_name=payload["last_name"].strip(),
            phone=payload.get("phone"),
            role=UserRole.CLINICA,
            clinic_id=clinic.id,
        )
        user.set_password(payload["password"])
        db.session.add(user)
        db.session.flush()

        db.session.commit()

        # Emitir tokens para auto-login
        tokens = AuthService.issue_tokens(user)

        return jsonify({
            "message": "Clínica registrada correctamente.",
            "clinic": {
                "id": clinic.id,
                "name": clinic.name,
                "slug": clinic.slug,
            },
            "user": tokens["user"],
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
        }), 201

    except ValidationError:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise ValidationError(str(e))


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
