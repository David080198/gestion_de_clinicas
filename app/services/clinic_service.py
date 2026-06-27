"""Servicio de gestion de clinicas (multi-tenancy).

Operaciones que el super-admin de la plataforma puede realizar:
    - Crear clinicas con subdominio unico.
    - Listar todas las clinicas.
    - Cambiar plan de una clinica.
    - Suspender/activar clinicas.
    - Asignar el primer admin de cada clinica.

Las clinicas se identifican por subdominio para el enrutamiento automatico.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import func, select

from app.exceptions import (
    AuthorizationError,
    DuplicateResourceError,
    RecordNotFoundError,
    ValidationError,
)
from app.extensions import db
from app.models import (
    Appointment,
    Clinic,
    ClinicPlan,
    ClinicStatus,
    Doctor,
    Patient,
    User,
    UserRole,
)

_SUBDOMAIN_REGEX: re.Pattern[str] = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$"
)


class ClinicService:
    """Operaciones de gestion de clinicas (super-admin)."""

    # ============================================================
    # Creacion de clinicas
    # ============================================================

    @staticmethod
    def create_clinic(payload: dict[str, Any]) -> Clinic:
        """Crea una nueva clinica en la plataforma.

        Args:
            payload: Datos validados por ClinicCreateSchema.

        Returns:
            La clinica creada.

        Raises:
            DuplicateResourceError: Si el subdominio ya existe.
            ValidationError: Si los datos son invalidos.
        """
        name: str = payload["name"].strip()
        subdomain: str = payload["subdomain"].lower().strip()

        # Validar subdominio
        if not _SUBDOMAIN_REGEX.match(subdomain):
            raise ValidationError(
                "Subdominio invalido: 2-60 caracteres, solo minusculas, "
                "numeros y guiones."
            )

        # Verificar unicidad
        existing: Optional[Clinic] = Clinic.find_by_subdomain(subdomain)
        if existing is not None:
            raise DuplicateResourceError(
                f"El subdominio {subdomain!r} ya esta en uso."
            )

        clinic = Clinic(
            name=name,
            slug=payload.get("slug", subdomain),
            subdomain=subdomain,
            plan=ClinicPlan(payload.get("plan", "starter")),
            status=ClinicStatus(payload.get("status", "prueba")),
            address=payload.get("address"),
            phone=payload.get("phone"),
            email=payload.get("email"),
            timezone=payload.get("timezone", "America/Mexico_City"),
            currency=payload.get("currency", "MXN"),
            logo_url=payload.get("logo_url"),
        )
        clinic.save()
        return clinic

    # ============================================================
    # Consulta
    # ============================================================

    @staticmethod
    def list_clinics(
        status: Optional[ClinicStatus] = None,
        plan: Optional[ClinicPlan] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Clinic], dict[str, Any]]:
        """Lista clinicas con filtros opcionales (super-admin)."""
        stmt = select(Clinic)
        if status is not None:
            stmt = stmt.where(Clinic.status == status)
        if plan is not None:
            stmt = stmt.where(Clinic.plan == plan)
        stmt = stmt.order_by(Clinic.created_at.desc())

        pagination = db.paginate(stmt, page=page, per_page=per_page)
        return list(pagination), {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        }

    @staticmethod
    def get_clinic(clinic_id: int) -> Clinic:
        """Recupera una clinica por id."""
        return Clinic.get_or_404(clinic_id)

    @staticmethod
    def get_clinic_stats(clinic_id: int) -> dict[str, Any]:
        """Retorna estadisticas de uso de una clinica.

        Utiles para verificar limites del plan y mostrar en el panel
        del super-admin.
        """
        clinic: Clinic = Clinic.get_or_404(clinic_id)

        doctor_count: int = db.session.scalar(
            select(func.count(Doctor.id)).where(Doctor.clinic_id == clinic_id)
        ) or 0
        patient_count: int = db.session.scalar(
            select(func.count(Patient.id)).where(Patient.clinic_id == clinic_id)
        ) or 0
        appointment_count: int = db.session.scalar(
            select(func.count(Appointment.id)).where(Appointment.clinic_id == clinic_id)
        ) or 0
        user_count: int = db.session.scalar(
            select(func.count(User.id)).where(User.clinic_id == clinic_id)
        ) or 0

        return {
            "clinic_id": clinic_id,
            "clinic_name": clinic.name,
            "plan": clinic.plan.value,
            "status": clinic.status.value,
            "usage": {
                "doctors": doctor_count,
                "patients": patient_count,
                "appointments": appointment_count,
                "users": user_count,
            },
            "limits": clinic.limits,
            "is_operational": clinic.is_operational,
        }

    # ============================================================
    # Gestion de plan y estado
    # ============================================================

    @staticmethod
    def change_plan(clinic_id: int, new_plan: ClinicPlan) -> Clinic:
        """Cambia el plan de una clinica.

        Si la clinica excede los limites del nuevo plan, se advierte pero
        se permite (el super-admin decide; el downgrade no elimina datos).
        """
        clinic: Clinic = Clinic.get_or_404(clinic_id)
        clinic.plan = new_plan
        db.session.commit()
        return clinic

    @staticmethod
    def change_status(clinic_id: int, new_status: ClinicStatus) -> Clinic:
        """Cambia el estado de una clinica (activar/suspender/cancelar).

        Al suspender una clinica, sus usuarios no podran acceder (el
        middleware de tenant lo bloquea via assert_clinic_operational).
        """
        clinic: Clinic = Clinic.get_or_404(clinic_id)
        clinic.status = new_status
        # Si se activa, tambien is_active=True
        if new_status in {ClinicStatus.ACTIVA, ClinicStatus.PRUEBA}:
            clinic.is_active = True
        elif new_status == ClinicStatus.SUSPENDIDA:
            clinic.is_active = False
        elif new_status == ClinicStatus.CANCELADA:
            clinic.is_active = False
        db.session.commit()
        return clinic

    @staticmethod
    def suspend(clinic_id: int) -> Clinic:
        """Atajo para suspender una clinica."""
        return ClinicService.change_status(clinic_id, ClinicStatus.SUSPENDIDA)

    @staticmethod
    def activate(clinic_id: int) -> Clinic:
        """Atajo para activar una clinica."""
        return ClinicService.change_status(clinic_id, ClinicStatus.ACTIVA)

    # ============================================================
    # Asignacion del primer admin de clinica
    # ============================================================

    @staticmethod
    def create_clinic_admin(
        clinic_id: int, payload: dict[str, Any]
    ) -> User:
        """Crea el primer usuario admin de una clinica.

        Este usuario podra luego crear medicos, recepcionistas y gestionar
        la clinica a nivel operativo.

        Args:
            clinic_id: Clinica a la que pertenece el admin.
            payload: {email, password, first_name, last_name, phone}

        Returns:
            El usuario admin creado.
        """
        clinic: Clinic = Clinic.get_or_404(clinic_id)

        email: str = payload["email"].lower().strip()
        existing: Optional[User] = db.session.scalar(
            select(User).where(User.email == email)
        )
        if existing is not None:
            raise DuplicateResourceError(
                f"El email {email!r} ya esta registrado."
            )

        admin = User(
            email=email,
            first_name=payload["first_name"].strip(),
            last_name=payload["last_name"].strip(),
            phone=payload.get("phone"),
            role=UserRole.ADMIN,
            clinic_id=clinic_id,
        )
        admin.set_password(payload["password"])
        db.session.add(admin)
        db.session.commit()
        return admin

    # ============================================================
    # Registro de clinica (self-service)
    # ============================================================

    @staticmethod
    def register_new_clinic(payload: dict[str, Any]) -> dict[str, Any]:
        """Flujo de auto-registro: crea clinica + su primer admin.

        Usado cuando una clinica se registra sola desde la landing page.
        La clinica se crea en estado PRUEBA con plan STARTER.

        Args:
            payload: {
                clinic_name, subdomain, timezone, currency,
                admin_email, admin_password, admin_first_name, admin_last_name
            }

        Returns:
            dict con la clinica y el admin creados.
        """
        # 1. Crear clinica
        clinic = ClinicService.create_clinic({
            "name": payload["clinic_name"],
            "subdomain": payload["subdomain"],
            "plan": "starter",
            "status": "prueba",
            "timezone": payload.get("timezone", "America/Mexico_City"),
            "currency": payload.get("currency", "MXN"),
        })

        # 2. Crear admin
        admin = ClinicService.create_clinic_admin(clinic.id, {
            "email": payload["admin_email"],
            "password": payload["admin_password"],
            "first_name": payload["admin_first_name"],
            "last_name": payload["admin_last_name"],
        })

        return {
            "clinic": clinic.to_public_dict(),
            "admin": admin.to_public_dict(),
            "message": "Clinica registrada. Tu cuenta esta en periodo de prueba.",
        }

    # ============================================================
    # Actualizacion
    # ============================================================

    @staticmethod
    def update_clinic(clinic_id: int, payload: dict[str, Any]) -> Clinic:
        """Actualiza datos de una clinica (super-admin o admin de la clinica)."""
        clinic: Clinic = Clinic.get_or_404(clinic_id)

        if "name" in payload:
            clinic.name = payload["name"].strip()
        if "address" in payload:
            clinic.address = payload["address"]
        if "phone" in payload:
            clinic.phone = payload["phone"]
        if "email" in payload:
            clinic.email = payload["email"]
        if "logo_url" in payload:
            clinic.logo_url = payload["logo_url"]
        if "timezone" in payload:
            clinic.timezone = payload["timezone"]
        if "currency" in payload:
            clinic.currency = payload["currency"]

        db.session.commit()
        return clinic

    # ============================================================
    # Resolucion por subdominio
    # ============================================================

    @staticmethod
    def resolve_by_subdomain(subdomain: str) -> Optional[Clinic]:
        """Resuelve una clinica por su subdominio."""
        return Clinic.find_by_subdomain(subdomain)
