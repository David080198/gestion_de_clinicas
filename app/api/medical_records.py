"""Blueprint del expediente clinico y recetas electronicas.

Endpoints:
    POST /api/medical/appointments/<id>/record          - Crear expediente
    GET  /api/medical/records/<id>                       - Ver expediente
    GET  /api/medical/appointments/<id>/record           - Ver expediente por cita
    GET  /api/medical/patients/<id>/history              - Historial paciente
    POST /api/medical/records/<id>/prescriptions         - Emitir receta
    GET  /api/medical/prescriptions/<code>               - Ver receta
    GET  /api/medical/prescriptions/<code>/pdf           - Descargar PDF
    GET  /api/medical/patients/<id>/prescriptions        - Listar recetas paciente
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request, send_file
from io import BytesIO

from app.exceptions import ValidationError
from app.models import User
from app.schemas.medical_schemas import (
    MedicalRecordCreateSchema,
    MedicalRecordSchema,
    PrescriptionCreateSchema,
    PrescriptionSchema,
)
from app.services.medical_record_service import (
    MedicalRecordService,
    PrescriptionService,
)
from app.utils.decorators import current_user, login_required, medico_or_admin

medical_records_bp: Blueprint = Blueprint("medical_records", __name__)

# Schemas
_record_create_schema = MedicalRecordCreateSchema()
_record_schema = MedicalRecordSchema()
_record_schema_many = MedicalRecordSchema(many=True)
_rx_create_schema = PrescriptionCreateSchema()
_rx_schema = PrescriptionSchema()
_rx_schema_many = PrescriptionSchema(many=True)


# ============================================================
# Expediente clinico
# ============================================================

@medical_records_bp.route(
    "/appointments/<int:appointment_id>/record", methods=["POST"]
)
@medico_or_admin
def create_record(appointment_id: int):
    """Crea el expediente clinico de una cita (medico asignado o admin)."""
    payload: dict[str, Any] = _parse_json(_record_create_schema)
    user: User = current_user()
    record = MedicalRecordService.create_record(appointment_id, payload, user)
    return jsonify({
        "message": "Expediente creado.",
        "record": _enrich_record(_record_schema.dump(record), record),
    }), 201


@medical_records_bp.route("/records/<int:record_id>", methods=["GET"])
@login_required
def get_record(record_id: int):
    """Recupera un expediente por id (scope por rol)."""
    user: User = current_user()
    record = MedicalRecordService.get_record(record_id, user)
    return jsonify({
        "record": _enrich_record(_record_schema.dump(record), record)
    })


@medical_records_bp.route(
    "/appointments/<int:appointment_id>/record", methods=["GET"]
)
@login_required
def get_record_by_appointment(appointment_id: int):
    """Recupera el expediente asociado a una cita."""
    user: User = current_user()
    record = MedicalRecordService.get_record_by_appointment(appointment_id, user)
    return jsonify({
        "record": _enrich_record(_record_schema.dump(record), record)
    })


@medical_records_bp.route("/patients/<int:patient_id>/history", methods=["GET"])
@login_required
def patient_history(patient_id: int):
    """Historial cronologico del paciente (inmutable)."""
    user: User = current_user()
    records = MedicalRecordService.list_patient_history(patient_id, user)
    return jsonify({
        "items": [_enrich_record(_record_schema.dump(r), r) for r in records],
        "count": len(records),
    })


# ============================================================
# Recetas
# ============================================================

@medical_records_bp.route(
    "/records/<int:record_id>/prescriptions", methods=["POST"]
)
@medico_or_admin
def create_prescription(record_id: int):
    """Emite una receta asociada a un expediente."""
    payload: dict[str, Any] = _parse_json(_rx_create_schema)
    user: User = current_user()
    rx = PrescriptionService.create_prescription(record_id, payload, user)
    return jsonify({
        "message": "Receta emitida.",
        "prescription": _enrich_rx(_rx_schema.dump(rx), rx),
    }), 201


@medical_records_bp.route("/prescriptions/<string:code>", methods=["GET"])
@login_required
def get_prescription(code: str):
    """Recupera una receta por su codigo unico."""
    user: User = current_user()
    rx = PrescriptionService.get_prescription(code, user)
    return jsonify({
        "prescription": _enrich_rx(_rx_schema.dump(rx), rx)
    })


@medical_records_bp.route("/prescriptions/<string:code>/pdf", methods=["GET"])
@login_required
def download_prescription_pdf(code: str):
    """Descarga el PDF imprimible de una receta."""
    user: User = current_user()
    pdf_bytes: bytes = PrescriptionService.generate_pdf(code, user)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"receta_{code}.pdf",
    )


@medical_records_bp.route(
    "/patients/<int:patient_id>/prescriptions", methods=["GET"]
)
@login_required
def list_patient_prescriptions(patient_id: int):
    """Lista las recetas de un paciente."""
    user: User = current_user()
    rxs = PrescriptionService.list_patient_prescriptions(patient_id, user)
    return jsonify({
        "items": [_enrich_rx(_rx_schema.dump(r), r) for r in rxs],
        "count": len(rxs),
    })


# ============================================================
# Helpers
# ============================================================

def _parse_json(schema) -> dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("El cuerpo de la peticion debe ser JSON.")
    return schema.load(data)


def _enrich_record(data: dict[str, Any], record) -> dict[str, Any]:
    data["patient_name"] = record.patient.full_name if record.patient else None
    data["doctor_name"] = record.doctor.full_name if record.doctor else None
    return data


def _enrich_rx(data: dict[str, Any], rx) -> dict[str, Any]:
    data["patient_name"] = rx.patient.full_name if rx.patient else None
    data["doctor_name"] = rx.doctor.full_name if rx.doctor else None
    return data
