"""Blueprint de gestion de citas.

Endpoints:
    POST   /api/appointments                   - Crear cita
    GET    /api/appointments                   - Listar citas (filtros + scope)
    GET    /api/appointments/<id>              - Detalle de una cita
    PATCH  /api/appointments/<id>              - Reprogramar
    PATCH  /api/appointments/<id>/status       - Cambiar estado
    DELETE /api/appointments/<id>              - Cancelar cita
    GET    /api/appointments/calendar          - Vista calendario (rango)
    GET    /api/doctors/<id>/availability      - Slots disponibles
    GET    /api/doctors                         - Lista de medicos (publico)
    GET    /api/doctors/<id>                    - Detalle de un medico
    POST   /api/doctors                         - Crear medico (admin)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.exceptions import (
    AppointmentStateError,
    AuthorizationError,
    RecordNotFoundError,
    ValidationError,
)
from app.extensions import db
from app.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    User,
    UserRole,
)
from app.schemas.medical_schemas import (
    AppointmentCreateSchema,
    AppointmentSchema,
    AppointmentStatusSchema,
    AppointmentUpdateSchema,
    AvailabilityQuerySchema,
)
from app.schemas.user_schemas import DoctorPublicSchema, DoctorSchema
from app.services.appointment_service import AppointmentService
from app.utils.decorators import (
    admin_only,
    current_user,
    login_required,
    patient_or_above,
    receptionist_or_above,
)

appointments_bp: Blueprint = Blueprint("appointments", __name__)

# Schemas
_create_schema = AppointmentCreateSchema()
_update_schema = AppointmentUpdateSchema()
_status_schema = AppointmentStatusSchema()
_appointment_schema = AppointmentSchema()
_appointment_schema_many = AppointmentSchema(many=True)
_doctor_schema = DoctorSchema()
_doctor_public_schema = DoctorPublicSchema()
_doctor_public_schema_many = DoctorPublicSchema(many=True)
_availability_query = AvailabilityQuerySchema()


# ============================================================
# Citas
# ============================================================

@appointments_bp.route("", methods=["POST"])
@patient_or_above
def create_appointment():
    """Crea una nueva cita medica."""
    payload: dict[str, Any] = _parse_json(_create_schema)
    user: User = current_user()
    apt: Appointment = AppointmentService.create_appointment(payload, user)
    return jsonify({
        "message": "Cita creada correctamente.",
        "appointment": _enrich(_appointment_schema.dump(apt), apt),
    }), 201


@appointments_bp.route("", methods=["GET"])
@login_required
def list_appointments():
    """Lista citas paginadas con filtros y scope por rol."""
    user: User = current_user()
    page, per_page = _parse_pagination()
    doctor_id = _int_arg("doctor_id")
    patient_id = _int_arg("patient_id")
    status = _status_arg()
    start = _datetime_arg("start")
    end = _datetime_arg("end")

    items, meta = AppointmentService.list_appointments(
        acting_user=user,
        doctor_id=doctor_id,
        patient_id=patient_id,
        status=status,
        start=start,
        end=end,
        page=page,
        per_page=per_page,
    )
    return jsonify({
        "items": [_enrich(_appointment_schema.dump(a), a) for a in items],
        "meta": meta,
    })


@appointments_bp.route("/<int:appointment_id>", methods=["GET"])
@login_required
def get_appointment(appointment_id: int):
    """Detalle de una cita."""
    apt: Appointment = AppointmentService.get_appointment_or_404(appointment_id)
    _assert_can_view_appointment(apt, current_user())
    return jsonify({
        "appointment": _enrich(_appointment_schema.dump(apt), apt)
    })


@appointments_bp.route("/<int:appointment_id>", methods=["PATCH"])
@login_required
def reschedule_appointment(appointment_id: int):
    """Reprograma una cita (cambio de fecha/hora)."""
    payload: dict[str, Any] = _parse_json(_update_schema, partial=True)
    user: User = current_user()
    new_start = payload.get("start_time")
    new_end = payload.get("end_time")
    if not new_start or not new_end:
        raise ValidationError("start_time y end_time son requeridos para reprogramar.")

    apt = AppointmentService.reschedule(
        appointment_id,
        new_start,
        new_end,
        user,
    )
    return jsonify({
        "message": "Cita reprogramada.",
        "appointment": _enrich(_appointment_schema.dump(apt), apt),
    })


@appointments_bp.route("/<int:appointment_id>/status", methods=["PATCH"])
@login_required
def change_status(appointment_id: int):
    """Cambia el estado de una cita (maquina de estados)."""
    payload: dict[str, Any] = _parse_json(_status_schema)
    user: User = current_user()
    apt = AppointmentService.change_status(
        appointment_id, payload["status"], user
    )
    return jsonify({
        "message": "Estado actualizado.",
        "appointment": _enrich(_appointment_schema.dump(apt), apt),
    })


@appointments_bp.route("/<int:appointment_id>", methods=["DELETE"])
@login_required
def cancel_appointment(appointment_id: int):
    """Cancela una cita (atajo de cambio de estado)."""
    user: User = current_user()
    apt = AppointmentService.change_status(
        appointment_id, AppointmentStatus.CANCELADA, user
    )
    return jsonify({
        "message": "Cita cancelada.",
        "appointment": _enrich(_appointment_schema.dump(apt), apt),
    })


@appointments_bp.route("/calendar", methods=["GET"])
@login_required
def calendar():
    """Vista de calendario en un rango de fechas."""
    user: User = current_user()
    today: date = date.today()
    start: date = _date_arg("start") or today.replace(day=1)
    end: date = _date_arg("end") or (start + __import__("datetime").timedelta(days=30))

    apts: list[Appointment] = AppointmentService.list_calendar(user, start, end)
    return jsonify({
        "items": [_enrich(_appointment_schema.dump(a), a) for a in apts],
        "range": {"start": start.isoformat(), "end": end.isoformat()},
    })


# ============================================================
# Medicos y disponibilidad
# ============================================================

@appointments_bp.route("/doctors", methods=["GET"])
@login_required
def list_doctors():
    """Lista medicos activos (vista publica para agendar)."""
    doctors: list[Doctor] = list(
        db.session.scalars(
            select(Doctor).where(Doctor.is_available.is_(True)).order_by(Doctor.specialty)
        )
    )
    return jsonify({"items": _doctor_public_schema_many.dump(doctors)})


@appointments_bp.route("/doctors/<int:doctor_id>", methods=["GET"])
@login_required
def get_doctor(doctor_id: int):
    doctor: Doctor | None = db.session.get(Doctor, doctor_id)
    if doctor is None:
        raise RecordNotFoundError(f"Medico {doctor_id} no encontrado.")
    return jsonify({"doctor": _doctor_public_schema.dump(doctor)})


@appointments_bp.route("/doctors", methods=["POST"])
@admin_only
def create_doctor():
    """Crea un perfil de medico vinculado a un User existente (admin)."""
    from app.schemas.user_schemas import DoctorSchema as _DS
    payload: dict[str, Any] = _parse_json(_doctor_schema)
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        raise ValidationError("Query param 'user_id' es requerido.")
    user: User | None = db.session.get(User, user_id)
    if user is None:
        raise RecordNotFoundError(f"Usuario {user_id} no encontrado.")
    if user.role != UserRole.MEDICO:
        raise ValidationError("El usuario debe tener rol MEDICO.")

    existing: Doctor | None = db.session.scalar(
        select(Doctor).where(Doctor.user_id == user_id)
    )
    if existing is not None:
        raise ValidationError("El usuario ya tiene perfil de medico.")

    doctor = Doctor(
        user_id=user_id,
        license_number=payload["license_number"],
        specialty=payload["specialty"],
        bio=payload.get("bio"),
        consultation_fee=payload.get("consultation_fee"),
        is_available=payload.get("is_available", True),
    )
    doctor.save()
    return jsonify({
        "message": "Medico creado.",
        "doctor": _doctor_schema.dump(doctor),
    }), 201


@appointments_bp.route("/doctors/<int:doctor_id>/availability", methods=["GET"])
@login_required
def availability(doctor_id: int):
    """Slots disponibles para un medico en una fecha dada."""
    errors = _availability_query.validate(request.args)
    if errors:
        raise ValidationError("Parametros invalidos.", payload=errors)
    day: date = _date_arg("date") or date.today()
    slot_minutes: int = request.args.get("slot_minutes", type=int) or 30
    slots = AppointmentService.get_available_slots(doctor_id, day, slot_minutes)
    return jsonify({
        "doctor_id": doctor_id,
        "date": day.isoformat(),
        "slot_minutes": slot_minutes,
        "slots": slots,
    })


# ============================================================
# Helpers
# ============================================================

def _parse_json(schema, partial: bool = False) -> dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("El cuerpo de la peticion debe ser JSON.")
    return schema.load(data, partial=partial)


def _parse_pagination() -> tuple[int, int]:
    from app.utils.pagination import parse_pagination
    return parse_pagination()


def _int_arg(name: str) -> int | None:
    return request.args.get(name, type=int)


def _status_arg() -> AppointmentStatus | None:
    raw: str | None = request.args.get("status")
    if not raw:
        return None
    try:
        return AppointmentStatus(raw.lower())
    except ValueError:
        raise ValidationError(f"Estado invalido: {raw}")


def _datetime_arg(name: str) -> datetime | None:
    raw: str | None = request.args.get(name)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise ValidationError(f"Fecha invalida para {name}: {raw}")


def _date_arg(name: str) -> date | None:
    raw: str | None = request.args.get(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationError(f"Fecha invalida para {name}: {raw}")


def _enrich(data: dict[str, Any], apt: Appointment) -> dict[str, Any]:
    """Anade nombres de paciente/medico al dump del schema."""
    data["patient_name"] = apt.patient.full_name if apt.patient else None
    data["doctor_name"] = apt.doctor.full_name if apt.doctor else None
    data["doctor_specialty"] = apt.doctor.specialty if apt.doctor else None
    return data


def _assert_can_view_appointment(apt: Appointment, user: User) -> None:
    """Scope de lectura de una cita."""
    if user.is_admin or user.role == UserRole.RECEPCIONISTA:
        return
    if user.role == UserRole.MEDICO:
        if not user.doctor_profile or user.doctor_profile.id != apt.doctor_id:
            raise AuthorizationError("Solo puedes ver tus propias citas.")
        return
    if user.role == UserRole.PACIENTE:
        if not user.patient_profile or user.patient_profile.id != apt.patient_id:
            raise AuthorizationError("Solo puedes ver tus propias citas.")
        return
    raise AuthorizationError("No tienes permiso para ver esta cita.")
