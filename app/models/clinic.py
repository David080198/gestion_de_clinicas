"""Modelo Clinic: representa una clinica/consultorio cliente (tenant).

Cada clinica es un tenant independiente con sus propios usuarios, medicos,
pacientes, citas y expedientes. El aislamiento se logra mediante clinic_id
en todos los modelos (shared database, shared schema).

Una clinica se identifica por:
    - Subdominio unico (ej: clinica1.medcenter.app)
    - Slug unico (para URLs y referencias internas)
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import Boolean, Enum, Index, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.exceptions import DuplicateResourceError, ValidationError
from app.extensions import db
from .base import BaseModel
from .tenant_enums import ClinicPlan, ClinicStatus, PLAN_LIMITS

# Validacion de subdominio (solo minusculas, numeros, guiones)
_SUBDOMAIN_REGEX: re.Pattern[str] = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")


class Clinic(BaseModel):
    """Clinica/consultorio cliente de la plataforma (tenant).

    Attributes:
        name: Nombre comercial de la clinica.
        slug: Identificador unico para URLs (ej: "clinica-san-angel").
        subdomain: Subdominio unico (ej: "clinica-san-angel").
        plan: Plan contratado (starter, professional, clinic, enterprise).
        status: Estado de la clinica (activa, suspendida, prueba, cancelada).
        logo_url: URL del logo de la clinica (opcional).
        address: Direccion fisica.
        phone: Telefono de contacto.
        email: Email administrativo de la clinica.
        timezone: Zona horaria (ej: America/Mexico_City).
        currency: Moneda (ej: MXN, USD, EUR).
        is_active: Indica si la clinica puede operar (campo de negocio).
    """

    __tablename__ = "clinics"
    __table_args__ = (
        Index("ix_clinics_subdomain", "subdomain", unique=True),
        Index("ix_clinics_slug", "slug", unique=True),
        Index("ix_clinics_status", "status"),
    )

    # --- Identidad ---
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    subdomain: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)

    # --- Plan y estado ---
    plan: Mapped[ClinicPlan] = mapped_column(
        Enum(ClinicPlan, name="clinic_plan"),
        nullable=False,
        default=ClinicPlan.STARTER,
    )
    status: Mapped[ClinicStatus] = mapped_column(
        Enum(ClinicStatus, name="clinic_status"),
        nullable=False,
        default=ClinicStatus.PRUEBA,
    )

    # --- Branding ---
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # --- Contacto ---
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="America/Mexico_City")
    currency: Mapped[str] = mapped_column(String(10), default="MXN")

    # --- Negocio ---
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Relaciones ---
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="clinic", cascade="all, delete-orphan"
    )
    patients: Mapped[list["Patient"]] = relationship(
        "Patient", back_populates="clinic", cascade="all, delete-orphan"
    )
    doctors: Mapped[list["Doctor"]] = relationship(
        "Doctor", back_populates="clinic"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="clinic"
    )

    def __repr__(self) -> str:
        return f"<Clinic id={self.id} slug={self.slug!r} plan={self.plan.value}>"

    # ============================================================
    # Propiedades derivadas
    # ============================================================

    @property
    def limits(self) -> dict[str, int]:
        """Retorna los limites del plan actual."""
        return PLAN_LIMITS.get(self.plan, PLAN_LIMITS[ClinicPlan.STARTER])

    @property
    def is_operational(self) -> bool:
        """Indica si la clinica puede operar (activa o en prueba)."""
        return self.is_active and self.status in {
            ClinicStatus.ACTIVA,
            ClinicStatus.PRUEBA,
        }

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = super().to_dict(exclude=exclude)
        data["plan"] = self.plan.value
        data["status"] = self.status.value
        data["limits"] = self.limits
        data["is_operational"] = self.is_operational
        return data

    def to_public_dict(self) -> dict[str, Any]:
        """Vista publica de la clinica (para landing pages / registro)."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "subdomain": self.subdomain,
            "logo_url": self.logo_url,
            "plan": self.plan.value,
            "is_operational": self.is_operational,
        }

    # ============================================================
    # Validacion de limites del plan
    # ============================================================

    def check_doctor_limit(self, current_count: int) -> None:
        """Verifica que la clinica pueda agregar otro medico.

        Raises:
            ValidationError: Si se alcanzo el limite del plan.
        """
        max_doctors: int = self.limits["max_doctors"]
        if max_doctors != -1 and current_count >= max_doctors:
            raise ValidationError(
                f"Tu plan {self.plan.value} permite maximo {max_doctors} medicos. "
                f"Actualiza tu plan para agregar mas."
            )

    def check_patient_limit(self, current_count: int) -> None:
        """Verifica que la clinica pueda agregar otro paciente.

        Raises:
            ValidationError: Si se alcanzo el limite del plan.
        """
        max_patients: int = self.limits["max_patients"]
        if max_patients != -1 and current_count >= max_patients:
            raise ValidationError(
                f"Tu plan {self.plan.value} permite maximo {max_patients} pacientes. "
                f"Actualiza tu plan para agregar mas."
            )

    # ============================================================
    # Consultas
    # ============================================================

    @classmethod
    def find_by_subdomain(cls, subdomain: str) -> Optional["Clinic"]:
        """Busca una clinica por su subdominio unico."""
        return db.session.scalar(
            db.select(cls).where(cls.subdomain == subdomain.lower().strip())
        )

    @classmethod
    def find_by_slug(cls, slug: str) -> Optional["Clinic"]:
        """Busca una clinica por su slug unico."""
        return db.session.scalar(
            db.select(cls).where(cls.slug == slug.lower().strip())
        )

    @classmethod
    def get_or_404(cls, clinic_id: int) -> "Clinic":
        """Recupera una clinica por id o lanza RecordNotFoundError."""
        from app.exceptions import RecordNotFoundError

        clinic: Optional[Clinic] = db.session.get(cls, clinic_id)
        if clinic is None:
            raise RecordNotFoundError(f"Clinica {clinic_id} no encontrada.")
        return clinic


# ============================================================
# Validaciones a nivel de modelo
# ============================================================

@event.listens_for(Clinic, "before_insert")
@event.listens_for(Clinic, "before_update")
def _validate_clinic(mapper, connection, target: Clinic) -> None:
    """Valida coherencia de los datos de la clinica antes de persistir."""
    # Nombre obligatorio
    if not target.name or not target.name.strip():
        raise ValidationError("El nombre de la clinica es obligatorio.")

    # Subdominio: formato valido
    if not target.subdomain or not _SUBDOMAIN_REGEX.match(target.subdomain):
        raise ValidationError(
            "El subdominio debe tener 2-60 caracteres, solo minusculas, "
            "numeros y guiones (no puede empezar ni terminar con guion)."
        )

    # Slug = subdominio por defecto (si no se especifica)
    if not target.slug:
        target.slug = target.subdomain

    # Unicidad de subdominio (validacion amigable antes del constraint de BD)
    existing: Optional[Clinic] = Clinic.find_by_subdomain(target.subdomain)
    if existing is not None and existing.id != getattr(target, "id", None):
        raise DuplicateResourceError(
            f"El subdominio {target.subdomain!r} ya esta en uso."
        )
