"""Blueprint de gestion de clinicas (multi-tenancy).

Endpoints del super-admin (gestor de la plataforma):
    POST   /api/clinics                  - Crear clinica
    GET    /api/clinics                  - Listar clinicas
    GET    /api/clinics/<id>             - Detalle de clinica
    PATCH  /api/clinics/<id>             - Actualizar clinica
    PATCH  /api/clinics/<id>/plan        - Cambiar plan
    PATCH  /api/clinics/<id>/status      - Cambiar estado (suspender/activar)
    GET    /api/clinics/<id>/stats       - Estadisticas de uso
    POST   /api/clinics/<id>/admin       - Crear admin de la clinica

Endpoint publico (auto-registro desde landing page):
    POST   /api/clinics/register         - Registrar nueva clinica + admin
    GET    /api/clinics/resolve          - Resolver clinica por subdominio
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from app.exceptions import ValidationError
from app.schemas.clinic_schemas import (
    ChangePlanSchema,
    ChangeStatusSchema,
    ClinicAdminSchema,
    ClinicCreateSchema,
    ClinicRegisterSchema,
    ClinicSchema,
    ClinicStatsSchema,
    ClinicUpdateSchema,
)
from app.services.clinic_service import ClinicService
from app.utils.decorators import super_admin_only, login_required
from app.utils.pagination import parse_pagination
from app.utils.tenant import resolve_clinic_from_request

clinics_bp: Blueprint = Blueprint("clinics", __name__)

# Schemas
_create_schema = ClinicCreateSchema()
_update_schema = ClinicUpdateSchema()
_register_schema = ClinicRegisterSchema()
_admin_schema = ClinicAdminSchema()
_clinic_schema = ClinicSchema()
_clinic_schema_many = ClinicSchema(many=True)
_stats_schema = ClinicStatsSchema()
_plan_schema = ChangePlanSchema()
_status_schema = ChangeStatusSchema()


# ============================================================
# Endpoints del super-admin
# ============================================================

@clinics_bp.route("", methods=["POST"])
@super_admin_only
def create_clinic():
    """Crea una nueva clinica en la plataforma."""
    payload: dict[str, Any] = _parse_json(_create_schema)
    clinic = ClinicService.create_clinic(payload)
    return jsonify({
        "message": "Clinica creada correctamente.",
        "clinic": _clinic_schema.dump(clinic),
    }), 201


@clinics_bp.route("", methods=["GET"])
@super_admin_only
def list_clinics():
    """Lista todas las clinicas de la plataforma (super-admin)."""
    page, per_page = parse_pagination()
    status = request.args.get("status")
    plan = request.args.get("plan")

    from app.models import ClinicPlan, ClinicStatus
    status_filter = None
    plan_filter = None
    if status:
        try:
            status_filter = ClinicStatus(status)
        except ValueError:
            raise ValidationError(f"Estado invalido: {status}")
    if plan:
        try:
            plan_filter = ClinicPlan(plan)
        except ValueError:
            raise ValidationError(f"Plan invalido: {plan}")

    clinics, meta = ClinicService.list_clinics(
        status=status_filter, plan=plan_filter, page=page, per_page=per_page
    )
    return jsonify({
        "items": _clinic_schema_many.dump(clinics),
        "meta": meta,
    })


@clinics_bp.route("/<int:clinic_id>", methods=["GET"])
@super_admin_only
def get_clinic(clinic_id: int):
    """Detalle de una clinica."""
    clinic = ClinicService.get_clinic(clinic_id)
    return jsonify({"clinic": _clinic_schema.dump(clinic)})


@clinics_bp.route("/<int:clinic_id>", methods=["PATCH"])
@super_admin_only
def update_clinic(clinic_id: int):
    """Actualiza datos de una clinica."""
    payload: dict[str, Any] = _parse_json(_update_schema, partial=True)
    clinic = ClinicService.update_clinic(clinic_id, payload)
    return jsonify({
        "message": "Clinica actualizada.",
        "clinic": _clinic_schema.dump(clinic),
    })


@clinics_bp.route("/<int:clinic_id>/plan", methods=["PATCH"])
@super_admin_only
def change_plan(clinic_id: int):
    """Cambia el plan de una clinica."""
    payload: dict[str, Any] = _parse_json(_plan_schema)
    clinic = ClinicService.change_plan(clinic_id, payload["plan"])
    return jsonify({
        "message": f"Plan actualizado a {clinic.plan.value}.",
        "clinic": _clinic_schema.dump(clinic),
    })


@clinics_bp.route("/<int:clinic_id>/status", methods=["PATCH"])
@super_admin_only
def change_status(clinic_id: int):
    """Cambia el estado de una clinica (activar/suspender/cancelar)."""
    payload: dict[str, Any] = _parse_json(_status_schema)
    clinic = ClinicService.change_status(clinic_id, payload["status"])
    return jsonify({
        "message": f"Estado actualizado a {clinic.status.value}.",
        "clinic": _clinic_schema.dump(clinic),
    })


@clinics_bp.route("/<int:clinic_id>/stats", methods=["GET"])
@super_admin_only
def clinic_stats(clinic_id: int):
    """Estadisticas de uso de una clinica."""
    stats = ClinicService.get_clinic_stats(clinic_id)
    return jsonify({"stats": stats})


@clinics_bp.route("/<int:clinic_id>/admin", methods=["POST"])
@super_admin_only
def create_clinic_admin(clinic_id: int):
    """Crea el primer admin de una clinica."""
    payload: dict[str, Any] = _parse_json(_admin_schema)
    admin = ClinicService.create_clinic_admin(clinic_id, payload)
    return jsonify({
        "message": "Admin de clinica creado.",
        "user": admin.to_public_dict(),
    }), 201


# ============================================================
# Endpoints publicos (auto-registro)
# ============================================================

@clinics_bp.route("/register", methods=["POST"])
def register_clinic():
    """Auto-registro de una nueva clinica desde la landing page.

    Crea la clinica en estado PRUEBA con plan STARTER + su primer admin.
    No requiere autenticacion (es el punto de entrada al SaaS).
    """
    payload: dict[str, Any] = _parse_json(_register_schema)
    result = ClinicService.register_new_clinic(payload)
    return jsonify(result), 201


@clinics_bp.route("/resolve", methods=["GET"])
def resolve_clinic():
    """Resuelve la clinica a partir del subdominio del Host header.

    Usado por el frontend para determinar que clinica mostrar en la
    landing page cuando se accede via subdominio.medcenter.app
    """
    # Prioridad: query param subdomain > Host header
    subdomain = request.args.get("subdomain")
    if subdomain:
        from app.models import Clinic
        clinic = Clinic.find_by_subdomain(subdomain)
    else:
        clinic = resolve_clinic_from_request()

    if clinic is None:
        return jsonify({"clinic": None, "message": "Dominio principal o clinica no encontrada."}), 404

    return jsonify({"clinic": clinic.to_public_dict()})


# ============================================================
# Helper
# ============================================================

def _parse_json(schema, partial: bool = False) -> dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("El cuerpo de la peticion debe ser JSON.")
    return schema.load(data, partial=partial)
