"""Schemas de Clinica (multi-tenancy)."""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.models import ClinicPlan, ClinicStatus


class ClinicCreateSchema(Schema):
    """Payload para crear una clinica (super-admin)."""

    name = fields.Str(required=True, validate=validate.Length(min=2, max=200))
    subdomain = fields.Str(
        required=True,
        validate=validate.Regexp(
            r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$",
            error="Solo minusculas, numeros y guiones (2-60 chars).",
        ),
    )
    slug = fields.Str(load_default=None, validate=validate.Length(max=60))
    plan = fields.Enum(ClinicPlan, by_value=True, load_default=ClinicPlan.STARTER)
    status = fields.Enum(ClinicStatus, by_value=True, load_default=ClinicStatus.PRUEBA)
    address = fields.Str(load_default=None, validate=validate.Length(max=255))
    phone = fields.Str(load_default=None, validate=validate.Length(max=30))
    email = fields.Email(load_default=None)
    timezone = fields.Str(load_default="America/Mexico_City")
    currency = fields.Str(load_default="MXN")
    logo_url = fields.Str(load_default=None, validate=validate.Length(max=500))


class ClinicUpdateSchema(Schema):
    """Payload para actualizar datos de una clinica."""

    name = fields.Str(required=False, validate=validate.Length(min=2, max=200))
    address = fields.Str(required=False, load_default=None)
    phone = fields.Str(required=False, load_default=None)
    email = fields.Email(required=False, load_default=None)
    logo_url = fields.Str(required=False, load_default=None)
    timezone = fields.Str(required=False)
    currency = fields.Str(required=False)


class ClinicRegisterSchema(Schema):
    """Payload para auto-registro de una clinica nueva (landing page)."""

    # Datos de la clinica
    clinic_name = fields.Str(required=True, validate=validate.Length(min=2, max=200))
    subdomain = fields.Str(
        required=True,
        validate=validate.Regexp(
            r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$",
            error="Solo minusculas, numeros y guiones (2-60 chars).",
        ),
    )
    timezone = fields.Str(load_default="America/Mexico_City")
    currency = fields.Str(load_default="MXN")

    # Datos del admin
    admin_email = fields.Email(required=True)
    admin_password = fields.Str(
        required=True, load_only=True, validate=validate.Length(min=8, max=128)
    )
    admin_first_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    admin_last_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))


class ClinicAdminSchema(Schema):
    """Payload para crear el admin de una clinica."""

    email = fields.Email(required=True)
    password = fields.Str(
        required=True, load_only=True, validate=validate.Length(min=8, max=128)
    )
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    phone = fields.Str(load_default=None, validate=validate.Length(max=30))


class ClinicSchema(Schema):
    """Schema de salida de una clinica."""

    id = fields.Integer(dump_only=True)
    name = fields.Str(dump_only=True)
    slug = fields.Str(dump_only=True)
    subdomain = fields.Str(dump_only=True)
    plan = fields.Enum(ClinicPlan, by_value=True, dump_only=True)
    status = fields.Enum(ClinicStatus, by_value=True, dump_only=True)
    logo_url = fields.Str(dump_only=True, allow_none=True)
    address = fields.Str(dump_only=True, allow_none=True)
    phone = fields.Str(dump_only=True, allow_none=True)
    email = fields.Str(dump_only=True, allow_none=True)
    timezone = fields.Str(dump_only=True)
    currency = fields.Str(dump_only=True)
    is_active = fields.Boolean(dump_only=True)
    is_operational = fields.Boolean(dump_only=True)
    limits = fields.Dict(dump_only=True)
    created_at = fields.DateTime(dump_only=True, format="iso")


class ClinicStatsSchema(Schema):
    """Schema de estadisticas de uso de una clinica."""

    clinic_id = fields.Integer(dump_only=True)
    clinic_name = fields.Str(dump_only=True)
    plan = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    usage = fields.Dict(dump_only=True)
    limits = fields.Dict(dump_only=True)
    is_operational = fields.Boolean(dump_only=True)


class ChangePlanSchema(Schema):
    """Payload para cambiar el plan de una clinica."""

    plan = fields.Enum(ClinicPlan, by_value=True, required=True)


class ChangeStatusSchema(Schema):
    """Payload para cambiar el estado de una clinica."""

    status = fields.Enum(ClinicStatus, by_value=True, required=True)
