"""Schemas de usuario, paciente y medico."""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.models import Gender, UserRole


class UserSchema(Schema):
    """Schema publico de un usuario (sin password_hash)."""

    id = fields.Integer(dump_only=True)
    email = fields.Email(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    phone = fields.Str(load_default=None, validate=validate.Length(max=30))
    role = fields.Enum(UserRole, by_value=True, dump_only=True)
    is_active = fields.Boolean(dump_only=True)
    full_name = fields.Str(dump_only=True)


class RegisterSchema(Schema):
    """Payload de registro (paciente por defecto o rol indicado por admin)."""

    email = fields.Email(required=True)
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, max=128),
    )
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    phone = fields.Str(load_default=None, validate=validate.Length(max=30))
    role = fields.Enum(
        UserRole, by_value=True, load_default=UserRole.PACIENTE
    )

    # Datos del paciente (requeridos solo si role == PACIENTE)
    document_number = fields.Str(load_default=None, validate=validate.Length(max=50))
    birth_date = fields.Date(load_default=None, format="iso")
    gender = fields.Enum(Gender, by_value=True, load_default=Gender.NO_ESPECIFICADO)
    blood_type = fields.Str(load_default=None)
    allergies = fields.Str(load_default=None, validate=validate.Length(max=500))
    address = fields.Str(load_default=None, validate=validate.Length(max=255))
    emergency_contact_name = fields.Str(load_default=None, validate=validate.Length(max=120))
    emergency_contact_phone = fields.Str(load_default=None, validate=validate.Length(max=30))

    @validates_schema
    def _validate_patient_fields(self, data, **kwargs):
        role = data.get("role", UserRole.PACIENTE)
        if role == UserRole.PACIENTE and not data.get("document_number"):
            raise ValidationError(
                {"document_number": "El documento es obligatorio para pacientes."}
            )


class LoginSchema(Schema):
    """Payload de inicio de sesion."""

    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)


class PatientSchema(Schema):
    """Schema de un paciente."""

    id = fields.Integer(dump_only=True)
    user_id = fields.Integer(dump_only=True)
    document_number = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    birth_date = fields.Date(required=False, format="iso", allow_none=True)
    gender = fields.Enum(Gender, by_value=True)
    blood_type = fields.Str(load_default=None)
    address = fields.Str(load_default=None, validate=validate.Length(max=255))
    emergency_contact_name = fields.Str(load_default=None, validate=validate.Length(max=120))
    emergency_contact_phone = fields.Str(load_default=None, validate=validate.Length(max=30))
    allergies = fields.Str(load_default=None, validate=validate.Length(max=500))
    full_name = fields.Str(dump_only=True)
    age = fields.Integer(dump_only=True, allow_none=True)


class DoctorSchema(Schema):
    """Schema de un medico."""

    id = fields.Integer(dump_only=True)
    user_id = fields.Integer(dump_only=True)
    license_number = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    specialty = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    bio = fields.Str(load_default=None, validate=validate.Length(max=2000))
    consultation_fee = fields.Decimal(load_default=None, as_string=True, places=2)
    is_available = fields.Boolean(load_default=True)
    full_name = fields.Str(dump_only=True)


class DoctorPublicSchema(Schema):
    """Vista publica del medico (para pacientes al agendar)."""

    id = fields.Integer(dump_only=True)
    full_name = fields.Str(dump_only=True)
    specialty = fields.Str(dump_only=True)
    consultation_fee = fields.Decimal(as_string=True, places=2, dump_only=True)
    is_available = fields.Boolean(dump_only=True)
