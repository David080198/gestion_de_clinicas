"""Schemas de citas, expediente clinico y recetas."""

from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.models import AppointmentStatus, Weekday


class AppointmentCreateSchema(Schema):
    """Payload para crear una cita."""

    patient_id = fields.Integer(required=True)
    doctor_id = fields.Integer(required=True)
    start_time = fields.DateTime(required=True, format="iso")
    end_time = fields.DateTime(required=True, format="iso")
    reason = fields.Str(load_default=None, validate=validate.Length(max=500))
    notes = fields.Str(load_default=None, validate=validate.Length(max=2000))


class AppointmentUpdateSchema(Schema):
    """Payload para actualizar/reprogramar una cita (campos opcionales)."""

    start_time = fields.DateTime(required=False, format="iso")
    end_time = fields.DateTime(required=False, format="iso")
    reason = fields.Str(required=False, validate=validate.Length(max=500))
    notes = fields.Str(required=False, validate=validate.Length(max=2000))


class AppointmentStatusSchema(Schema):
    """Payload para transitar el estado de una cita."""

    status = fields.Enum(
        AppointmentStatus, by_value=True, required=True
    )


class AppointmentSchema(Schema):
    """Schema de salida de una cita."""

    id = fields.Integer(dump_only=True)
    patient_id = fields.Integer(dump_only=True)
    doctor_id = fields.Integer(dump_only=True)
    receptionist_id = fields.Integer(dump_only=True, allow_none=True)
    start_time = fields.DateTime(dump_only=True, format="iso")
    end_time = fields.DateTime(dump_only=True, format="iso")
    status = fields.Enum(AppointmentStatus, by_value=True, dump_only=True)
    reason = fields.Str(dump_only=True, allow_none=True)
    notes = fields.Str(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True, format="iso")
    # Campos expandibles (opcional segun include)
    patient_name = fields.Str(dump_only=True)
    doctor_name = fields.Str(dump_only=True)
    doctor_specialty = fields.Str(dump_only=True)


class CalendarQuerySchema(Schema):
    """Query params del calendario (rango de fechas)."""

    doctor_id = fields.Integer(required=False)
    start = fields.Date(required=False, format="iso")
    end = fields.Date(required=False, format="iso")


class AvailabilityQuerySchema(Schema):
    """Query params para disponibilidad de un medico en una fecha."""

    date = fields.Date(required=True, format="iso")
    slot_minutes = fields.Integer(load_default=30, validate=validate.Range(min=5, max=480))


# ============================================================
# Expediente clinico
# ============================================================

class MedicalRecordCreateSchema(Schema):
    """Payload para crear un expediente clinico."""

    reason = fields.Str(load_default=None, validate=validate.Length(max=500))
    symptoms = fields.Str(load_default=None, validate=validate.Length(max=5000))
    blood_pressure = fields.Str(load_default=None, validate=validate.Length(max=20))
    temperature = fields.Float(
        load_default=None, validate=validate.Range(min=30.0, max=45.0)
    )
    heart_rate = fields.Integer(
        load_default=None, validate=validate.Range(min=20, max=250)
    )
    weight = fields.Float(
        load_default=None, validate=validate.Range(min=0.1, max=500.0)
    )
    height = fields.Float(
        load_default=None, validate=validate.Range(min=20.0, max=250.0)
    )
    diagnosis = fields.Str(load_default=None, validate=validate.Length(max=5000))
    treatment = fields.Str(load_default=None, validate=validate.Length(max=5000))
    notes = fields.Str(load_default=None, validate=validate.Length(max=5000))


class MedicalRecordSchema(Schema):
    """Schema de salida del expediente clinico."""

    id = fields.Integer(dump_only=True)
    appointment_id = fields.Integer(dump_only=True)
    patient_id = fields.Integer(dump_only=True)
    doctor_id = fields.Integer(dump_only=True)
    reason = fields.Str(dump_only=True, allow_none=True)
    symptoms = fields.Str(dump_only=True, allow_none=True)
    blood_pressure = fields.Str(dump_only=True, allow_none=True)
    temperature = fields.Float(dump_only=True, allow_none=True)
    heart_rate = fields.Integer(dump_only=True, allow_none=True)
    weight = fields.Float(dump_only=True, allow_none=True)
    height = fields.Float(dump_only=True, allow_none=True)
    diagnosis = fields.Str(dump_only=True, allow_none=True)
    treatment = fields.Str(dump_only=True, allow_none=True)
    notes = fields.Str(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True, format="iso")
    patient_name = fields.Str(dump_only=True)
    doctor_name = fields.Str(dump_only=True)


# ============================================================
# Recetas
# ============================================================

class MedicationItemSchema(Schema):
    """Un medicamento dentro de la receta."""

    name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    dose = fields.Str(load_default=None, validate=validate.Length(max=100))
    frequency = fields.Str(load_default=None, validate=validate.Length(max=100))
    duration = fields.Str(load_default=None, validate=validate.Length(max=100))
    instructions = fields.Str(load_default=None, validate=validate.Length(max=500))


class PrescriptionCreateSchema(Schema):
    """Payload para emitir una receta asociada a un expediente."""

    medications = fields.List(
        fields.Nested(MedicationItemSchema), required=True, validate=validate.Length(min=1, max=20)
    )
    notes = fields.Str(load_default=None, validate=validate.Length(max=2000))


class PrescriptionSchema(Schema):
    """Schema de salida de la receta."""

    id = fields.Integer(dump_only=True)
    code = fields.Str(dump_only=True)
    medical_record_id = fields.Integer(dump_only=True)
    patient_id = fields.Integer(dump_only=True)
    doctor_id = fields.Integer(dump_only=True)
    medications = fields.List(fields.Dict(), dump_only=True)
    notes = fields.Str(dump_only=True, allow_none=True)
    issued_at = fields.DateTime(dump_only=True, format="iso")
    item_count = fields.Integer(dump_only=True)
    patient_name = fields.Str(dump_only=True)
    doctor_name = fields.Str(dump_only=True)
