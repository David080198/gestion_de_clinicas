"""Servicio de dashboard: metricas personalizadas por rol.

    - Admin: ingresos mensuales, citas totales, medicos mas solicitados.
    - Medico: citas del dia, accesos rapidos.
    - Recepcionista: pacientes en sala de espera (citas confirmadas hoy).
    - Paciente: proximas citas y resumen de historial.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select

from app.exceptions import AuthorizationError
from app.extensions import db
from app.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    MedicalRecord,
    Patient,
    Prescription,
    User,
    UserRole,
)


class DashboardService:
    """Metricas agregadas para el panel de control."""

    # ============================================================
    # Dispatcher
    # ============================================================

    @staticmethod
    def get_metrics(user: User) -> dict[str, Any]:
        """Retorna las metricas correspondientes al rol del usuario."""
        if user.role == UserRole.ADMIN:
            return DashboardService._admin_metrics()
        if user.role == UserRole.MEDICO:
            return DashboardService._medico_metrics(user)
        if user.role == UserRole.RECEPCIONISTA:
            return DashboardService._receptionist_metrics()
        if user.role == UserRole.PACIENTE:
            return DashboardService._patient_metrics(user)
        raise AuthorizationError("Rol sin dashboard definido.")

    # ============================================================
    # Admin
    # ============================================================

    @staticmethod
    def _admin_metrics() -> dict[str, Any]:
        today: date = date.today()
        month_start: date = today.replace(day=1)

        # Citas totales del mes
        total_appointments: int = db.session.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.start_time >= datetime.combine(month_start, time.min),
                Appointment.start_time <= datetime.combine(today, time.max),
            )
        ) or 0

        # Citas por estado (mes actual)
        status_rows = db.session.execute(
            select(Appointment.status, func.count(Appointment.id))
            .where(
                Appointment.start_time >= datetime.combine(month_start, time.min),
                Appointment.start_time <= datetime.combine(today, time.max),
            )
            .group_by(Appointment.status)
        ).all()
        by_status: dict[str, int] = {
            row[0].value: int(row[1]) for row in status_rows
        }

        # Medicos mas solicitados (top 5 del mes)
        top_doctors = db.session.execute(
            select(
                Doctor.id,
                User.first_name,
                User.last_name,
                Doctor.specialty,
                func.count(Appointment.id).label("citas"),
            )
            .join(Appointment, Appointment.doctor_id == Doctor.id)
            .join(User, Doctor.user_id == User.id)
            .where(
                Appointment.start_time >= datetime.combine(month_start, time.min),
                Appointment.start_time <= datetime.combine(today, time.max),
                Appointment.status != AppointmentStatus.CANCELADA,
            )
            .group_by(Doctor.id, User.first_name, User.last_name, Doctor.specialty)
            .order_by(func.count(Appointment.id).desc())
            .limit(5)
        ).all()
        top_doctors_list: list[dict[str, Any]] = [
            {
                "doctor_id": row[0],
                "name": f"{row[1]} {row[2]}",
                "specialty": row[3],
                "appointments": int(row[4]),
            }
            for row in top_doctors
        ]

        # Ingresos estimados del mes (citas completadas * tarifa)
        revenue_rows = db.session.execute(
            select(Doctor.consultation_fee, func.count(Appointment.id))
            .join(Appointment, Appointment.doctor_id == Doctor.id)
            .where(
                Appointment.status == AppointmentStatus.COMPLETADA,
                Appointment.start_time >= datetime.combine(month_start, time.min),
                Appointment.start_time <= datetime.combine(today, time.max),
            )
            .group_by(Doctor.consultation_fee)
        ).all()
        revenue: float = sum(
            float(row[0] or 0) * int(row[1]) for row in revenue_rows
        )

        # Ingresos por mes (ultimos 6 meses)
        six_months_ago: date = (today - timedelta(days=180)).replace(day=1)
        monthly_rows = db.session.execute(
            select(
                func.extract("year", Appointment.start_time).label("y"),
                func.extract("month", Appointment.start_time).label("m"),
                Doctor.consultation_fee,
                func.count(Appointment.id).label("citas"),
            )
            .join(Appointment, Appointment.doctor_id == Doctor.id)
            .where(
                Appointment.status == AppointmentStatus.COMPLETADA,
                Appointment.start_time >= datetime.combine(six_months_ago, time.min),
            )
            .group_by("y", "m", Doctor.consultation_fee)
            .order_by("y", "m")
        ).all()
        monthly: dict[str, float] = {}
        for row in monthly_rows:
            key: str = f"{int(row[0])}-{int(row[1]):02d}"
            monthly[key] = monthly.get(key, 0.0) + float(row[2] or 0) * int(row[3])

        return {
            "role": "admin",
            "totals": {
                "appointments_this_month": total_appointments,
                "revenue_this_month": round(revenue, 2),
                "currency": "MXN",
            },
            "appointments_by_status": by_status,
            "top_doctors": top_doctors_list,
            "monthly_revenue": [
                {"month": k, "revenue": round(v, 2)} for k, v in monthly.items()
            ],
        }

    # ============================================================
    # Medico
    # ============================================================

    @staticmethod
    def _medico_metrics(user: User) -> dict[str, Any]:
        if not user.doctor_profile:
            return {"role": "medico", "today_appointments": []}
        doctor_id: int = user.doctor_profile.id
        today_start: datetime = datetime.combine(date.today(), time.min)
        today_end: datetime = datetime.combine(date.today(), time.max)

        todays: list[Appointment] = list(
            db.session.scalars(
                select(Appointment)
                .where(
                    Appointment.doctor_id == doctor_id,
                    Appointment.start_time >= today_start,
                    Appointment.start_time <= today_end,
                    Appointment.status != AppointmentStatus.CANCELADA,
                )
                .order_by(Appointment.start_time.asc())
            )
        )

        return {
            "role": "medico",
            "doctor_id": doctor_id,
            "today_appointments": [
                {
                    "id": a.id,
                    "start_time": a.start_time.isoformat(),
                    "end_time": a.end_time.isoformat(),
                    "patient_name": a.patient.full_name if a.patient else None,
                    "status": a.status.value,
                    "reason": a.reason,
                }
                for a in todays
            ],
            "counts": {
                "today": len(todays),
                "in_consultation": sum(
                    1 for a in todays if a.status == AppointmentStatus.EN_CONSULTA
                ),
                "completed_today": sum(
                    1 for a in todays if a.status == AppointmentStatus.COMPLETADA
                ),
            },
        }

    # ============================================================
    # Recepcionista
    # ============================================================

    @staticmethod
    def _receptionist_metrics() -> dict[str, Any]:
        today_start: datetime = datetime.combine(date.today(), time.min)
        today_end: datetime = datetime.combine(date.today(), time.max)

        # Sala de espera: citas confirmadas o en consulta de hoy
        waiting: list[Appointment] = list(
            db.session.scalars(
                select(Appointment)
                .where(
                    Appointment.start_time >= today_start,
                    Appointment.start_time <= today_end,
                    Appointment.status.in_([
                        AppointmentStatus.CONFIRMADA,
                        AppointmentStatus.EN_CONSULTA,
                    ]),
                )
                .order_by(Appointment.start_time.asc())
            )
        )
        total_today: int = db.session.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.start_time >= today_start,
                Appointment.start_time <= today_end,
                Appointment.status != AppointmentStatus.CANCELADA,
            )
        ) or 0

        return {
            "role": "recepcionista",
            "total_appointments_today": total_today,
            "waiting_room": [
                {
                    "id": a.id,
                    "patient_name": a.patient.full_name if a.patient else None,
                    "document_number": a.patient.document_number if a.patient else None,
                    "doctor_name": a.doctor.full_name if a.doctor else None,
                    "start_time": a.start_time.isoformat(),
                    "status": a.status.value,
                }
                for a in waiting
            ],
        }

    # ============================================================
    # Paciente
    # ============================================================

    @staticmethod
    def _patient_metrics(user: User) -> dict[str, Any]:
        if not user.patient_profile:
            return {"role": "paciente", "upcoming": [], "history_count": 0}
        patient_id: int = user.patient_profile.id
        now: datetime = datetime.now()

        upcoming: list[Appointment] = list(
            db.session.scalars(
                select(Appointment)
                .where(
                    Appointment.patient_id == patient_id,
                    Appointment.start_time >= now,
                    Appointment.status != AppointmentStatus.CANCELADA,
                )
                .order_by(Appointment.start_time.asc())
            )
        )
        history_count: int = db.session.scalar(
            select(func.count(MedicalRecord.id)).where(
                MedicalRecord.patient_id == patient_id
            )
        ) or 0
        prescriptions_count: int = db.session.scalar(
            select(func.count(Prescription.id)).where(
                Prescription.patient_id == patient_id
            )
        ) or 0

        return {
            "role": "paciente",
            "patient_id": patient_id,
            "upcoming": [
                {
                    "id": a.id,
                    "start_time": a.start_time.isoformat(),
                    "doctor_name": a.doctor.full_name if a.doctor else None,
                    "doctor_specialty": a.doctor.specialty if a.doctor else None,
                    "status": a.status.value,
                }
                for a in upcoming
            ],
            "counts": {
                "history_records": history_count,
                "prescriptions": prescriptions_count,
            },
        }
