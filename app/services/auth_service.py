"""Servicio de autenticacion: registro, login, logout y refresh.

Toda la logica de negocio de credenciales vive aqui para que los
endpoints solo se ocupen del transporte HTTP y las cookies JWT.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    unset_jwt_cookies,
)
from sqlalchemy import select

from app.exceptions import (
    AuthenticationError,
    DuplicateResourceError,
    ValidationError,
)
from app.extensions import db
from app.models import BloodType, Gender, Patient, User, UserRole


class AuthService:
    """Operaciones de autenticacion y gestion de cuentas."""

    # ============================================================
    # Registro
    # ============================================================

    @staticmethod
    def register(payload: dict[str, Any], acting_user: User | None = None) -> User:
        """Crea una nueva cuenta de usuario y, si es paciente, su perfil.

        Reglas RBAC:
            - Cualquiera puede registrar un PACIENTE (auto-registro).
            - Solo admin puede crear MEDICO, RECEPCIONISTA o ADMIN.

        Args:
            payload: Datos validados por RegisterSchema.
            acting_user: Usuario que ejecuta la accion (None en auto-registro).

        Returns:
            El usuario creado (sin commit; el endpoint decide).

        Raises:
            AuthorizationError: Si un no-admin intenta crear un rol superior.
            DuplicateResourceError: Si el email ya existe.
            ValidationError: Si falta el documento del paciente.
        """
        email: str = payload["email"].lower().strip()
        role: UserRole = payload.get("role", UserRole.PACIENTE)

        # --- Permisos ---
        if role != UserRole.PACIENTE:
            if acting_user is None or not acting_user.is_admin:
                raise AuthenticationError(
                    "Solo un administrador puede crear cuentas de staff."
                )

        # --- Unicidad de email ---
        exists: User | None = db.session.scalar(
            select(User).where(User.email == email)
        )
        if exists is not None:
            raise DuplicateResourceError(f"El email {email!r} ya esta registrado.")

        # --- Multi-tenancy: determinar clinic_id ---
        # Si el acting_user existe, hereda su clinic_id.
        # Si es auto-registro de paciente, se resuelve la clinica por subdominio.
        clinic_id: int | None = None
        if acting_user is not None:
            clinic_id = acting_user.clinic_id
        elif role == UserRole.PACIENTE:
            # Auto-registro: resolver clinica por subdominio del Host header
            from app.utils.tenant import resolve_clinic_from_request
            clinic = resolve_clinic_from_request()
            if clinic is not None:
                clinic_id = clinic.id
                # Verificar que la clinica este operativa
                if not clinic.is_operational:
                    raise ValidationError(
                        f"La clinica {clinic.name} no acepta registros en este momento."
                    )

        # --- Crear usuario ---
        user = User(
            email=email,
            first_name=payload["first_name"].strip(),
            last_name=payload["last_name"].strip(),
            phone=payload.get("phone"),
            role=role,
            clinic_id=clinic_id,
        )
        user.set_password(payload["password"])
        db.session.add(user)
        db.session.flush()  # obtiene el id sin commit definitivo

        # --- Perfil de paciente ---
        if role == UserRole.PACIENTE:
            document_number: str | None = payload.get("document_number")
            if not document_number:
                raise ValidationError("El documento es obligatorio para pacientes.")

            # Unicidad de documento DENTRO de la clinica
            doc_stmt = select(Patient).where(Patient.document_number == document_number)
            if clinic_id is not None:
                doc_stmt = doc_stmt.where(Patient.clinic_id == clinic_id)
            doc_exists: Patient | None = db.session.scalar(doc_stmt)
            if doc_exists is not None:
                raise DuplicateResourceError(
                    f"El documento {document_number!r} ya esta registrado en esta clinica."
                )

            blood_type: BloodType = _parse_blood_type(payload.get("blood_type"))
            patient = Patient(
                user_id=user.id,
                clinic_id=clinic_id,
                document_number=document_number,
                birth_date=payload.get("birth_date"),
                gender=payload.get("gender", Gender.NO_ESPECIFICADO),
                blood_type=blood_type,
                allergies=payload.get("allergies"),
                address=payload.get("address"),
                emergency_contact_name=payload.get("emergency_contact_name"),
                emergency_contact_phone=payload.get("emergency_contact_phone"),
            )
            db.session.add(patient)

        db.session.commit()
        return user

    # ============================================================
    # Login
    # ============================================================

    @staticmethod
    def authenticate(email: str, password: str) -> User:
        """Verifica credenciales y retorna el usuario.

        Raises:
            AuthenticationError: Si las credenciales son invalidas o la
                cuenta esta inactiva.
        """
        user: User | None = db.session.scalar(
            select(User).where(User.email == email.lower().strip())
        )
        if user is None or not user.check_password(password):
            raise AuthenticationError("Email o contrasena incorrectos.")
        if not user.is_active:
            raise AuthenticationError("La cuenta esta desactivada.")
        return user

    @staticmethod
    def issue_tokens(user: User) -> dict[str, Any]:
        """Genera los claims y tokens de acceso/refresh para el usuario.

        El identity es el id del usuario; los claims adicionales exponen
        el rol para que el frontend pueda reaccionar sin pedir /me.
        """
        additional_claims: dict[str, Any] = {
            "role": user.role.value,
            "email": user.email,
            "name": user.full_name,
        }
        access_token: str = create_access_token(
            identity=str(user.id),
            additional_claims=additional_claims,
        )
        refresh_token: str = create_refresh_token(
            identity=str(user.id),
            additional_claims=additional_claims,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user.to_public_dict(),
        }

    # ============================================================
    # Refresh
    # ============================================================

    @staticmethod
    def refresh_access_token() -> str:
        """Emite un nuevo access token a partir de un refresh token valido.

        Raises:
            AuthenticationError: Si el usuario ya no existe o esta inactivo.
        """
        identity: Any = get_jwt_identity()
        if identity is None:
            raise AuthenticationError("Token de refresco invalido.")
        user: User | None = User.get_by_id(int(identity))
        if user is None or not user.is_active:
            raise AuthenticationError("Usuario no valido para refresco.")

        additional_claims: dict[str, Any] = {
            "role": user.role.value,
            "email": user.email,
            "name": user.full_name,
        }
        return create_access_token(
            identity=str(user.id),
            additional_claims=additional_claims,
        )

    # ============================================================
    # Logout
    # ============================================================

    @staticmethod
    def revoke_current_tokens(response) -> None:
        """Elimina las cookies JWT de la respuesta (logout).

        Para invalidacion server-side se podria usar una lista de revocados
        (jti) en cache; por ahora se confia en la eliminacion de cookies.
        """
        unset_jwt_cookies(response)


# ============================================================
# Helpers privados
# ============================================================

def _parse_blood_type(value: str | None) -> BloodType:
    """Convierte un string de tipo de sangre al enum correspondiente."""
    if value is None:
        return BloodType.DESCONOCIDO
    for bt in BloodType:
        if bt.value.upper() == value.upper():
            return bt
    return BloodType.DESCONOCIDO
