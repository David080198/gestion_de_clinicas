"""Modelo User: autenticacion y control de acceso basado en roles (RBAC).

Un usuario representa una cuenta de acceso al sistema. Segun su rol puede
tener vinculado un perfil de paciente (PACIENTE) o de medico (MEDICO).
Los roles ADMIN y RECEPCIONISTA no requieren perfil adicional.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.exceptions import ValidationError
from .base import BaseModel
from .enums import UserRole

# Validacion basica de email (RFC 5322 simplificado)
_EMAIL_REGEX: re.Pattern[str] = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


class User(BaseModel):
    """Usuario del sistema con un rol asignado.

    Attributes:
        email: Correo unico y verificable del usuario.
        password_hash: Contrasena cifrada con Werkzeug/bcrypt.
        role: Rol dentro del sistema (RBAC).
        first_name: Nombre(s).
        last_name: Apellido(s).
        phone: Telefono de contacto en formato E.164 o local.
        is_active: Indica si la cuenta puede iniciar sesion.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
    )

    # --- Multi-tenancy: clinica a la que pertenece ---
    # nullable=True para compatibilidad con datos pre-Fase 5 y super-admins
    # que no pertenecen a ninguna clinica especifica.
    clinic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # --- Credenciales ---
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Identidad ---
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # --- RBAC ---
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.PACIENTE,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Relaciones ---
    clinic: Mapped[Optional["Clinic"]] = relationship("Clinic", back_populates="users")

    # --- Relaciones 1:1 con perfiles ---
    patient_profile: Mapped[Optional["Patient"]] = relationship(
        "Patient", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    doctor_profile: Mapped[Optional["Doctor"]] = relationship(
        "Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    # ============================================================
    # Propiedades e identidad
    # ============================================================

    @property
    def full_name(self) -> str:
        """Nombre completo del usuario."""
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} email={self.email!r} role={self.role.value}>"
        )

    # ============================================================
    # Hashing de contrasena (Werkzeug)
    # ============================================================

    def set_password(self, raw_password: str) -> None:
        """Cifra y almacena la contrasena del usuario.

        Args:
            raw_password: Contrasena en claro (minimo 8 caracteres).

        Raises:
            ValidationError: Si la contrasena no cumple el minimo de longitud.
        """
        if not raw_password or len(raw_password) < 8:
            raise ValidationError(
                "La contrasena debe tener al menos 8 caracteres."
            )
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(
            raw_password, method="pbkdf2:sha256", salt_length=16
        )

    def check_password(self, raw_password: str) -> bool:
        """Verifica la contrasena en claro contra el hash almacenado."""
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, raw_password)

    # ============================================================
    # Helpers de RBAC
    # ============================================================

    def has_role(self, *roles: UserRole | str) -> bool:
        """Indica si el usuario posee alguno de los roles indicados."""
        wanted: set[str] = {
            r.value if isinstance(r, UserRole) else str(r).lower() for r in roles
        }
        return self.role.value in wanted

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_medico(self) -> bool:
        return self.role == UserRole.MEDICO

    @property
    def is_recepcionista(self) -> bool:
        return self.role == UserRole.RECEPCIONISTA

    @property
    def is_paciente(self) -> bool:
        return self.role == UserRole.PACIENTE

    @property
    def is_super_admin(self) -> bool:
        """Super-admin: admin sin clinica (gestiona la plataforma completa)."""
        return self.role == UserRole.ADMIN and self.clinic_id is None

    @property
    def clinic_name(self) -> str:
        """Nombre de la clinica del usuario (o 'Plataforma' si es super-admin)."""
        if self.clinic:
            return self.clinic.name
        return "Plataforma"

    # ============================================================
    # Serializacion
    # ============================================================

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        exclude = (exclude or set()) | {"password_hash"}
        return super().to_dict(exclude=exclude)

    def to_public_dict(self) -> dict[str, Any]:
        """Vista publica segura (sin datos sensibles)."""
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role.value,
            "is_active": self.is_active,
        }


# ============================================================
# Validaciones a nivel de modelo
# ============================================================

@event.listens_for(User, "before_insert")
@event.listens_for(User, "before_update")
def _validate_user_email(mapper, connection, target: User) -> None:
    """Valida el formato del email antes de persistir el usuario."""
    if target.email and not _EMAIL_REGEX.match(target.email):
        raise ValidationError(f"Email invalido: {target.email!r}")
