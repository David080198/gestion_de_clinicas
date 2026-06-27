"""Modelo DoctorSchedule: horarios de atencion de cada medico.

Cada medico define franjas horarias por dia de la semana (ej: Lunes a Viernes
de 09:00 a 18:00 con intervalos de 30 min). Estas franjas se usan para
validar que una cita solicitada cae dentro del horario de atencion.
"""

from __future__ import annotations

from datetime import time
from typing import Any, Optional

from sqlalchemy import Enum, ForeignKey, Index, SmallInteger, Time, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.exceptions import OutOfScheduleError, ValidationError
from .base import BaseModel
from .enums import Weekday


class DoctorSchedule(BaseModel):
    """Franja horaria recurrente de atencion de un medico.

    Attributes:
        doctor_id: FK al Doctor.
        weekday: Dia de la semana (0=Lunes ... 6=Domingo).
        start_time: Hora de inicio de la franja (ej: 09:00).
        end_time: Hora de fin de la franja (ej: 18:00).
        slot_minutes: Duracion de cada cita en minutos (ej: 30).
        is_active: Indica si la franja esta vigente.
    """

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        UniqueConstraint(
            "doctor_id", "weekday", name="uq_doctor_schedule_doctor_weekday"
        ),
        Index("ix_doctor_schedule_doctor", "doctor_id"),
    )

    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[Weekday] = mapped_column(
        Enum(Weekday, name="weekday"), nullable=False
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_minutes: Mapped[int] = mapped_column(SmallInteger, default=30, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # --- Relaciones ---
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="schedules")

    def __repr__(self) -> str:
        return (
            f"<DoctorSchedule doctor={self.doctor_id} "
            f"day={self.weekday.name} {self.start_time}-{self.end_time}>"
        )

    # ============================================================
    # Validacion de horario
    # ============================================================

    def contains(self, start: time, end: time) -> bool:
        """Indica si una cita [start, end] cabe dentro de esta franja."""
        return self.start_time <= start and end <= self.end_time

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = super().to_dict(exclude=exclude)
        data["weekday"] = self.weekday.name
        data["start_time"] = self.start_time.isoformat()
        data["end_time"] = self.end_time.isoformat()
        return data


# ============================================================
# Validaciones a nivel de modelo
# ============================================================

@event.listens_for(DoctorSchedule, "before_insert")
@event.listens_for(DoctorSchedule, "before_update")
def _validate_schedule(mapper, connection, target: DoctorSchedule) -> None:
    """Valida coherencia del horario: inicio < fin y slot razonable."""
    if target.start_time >= target.end_time:
        raise ValidationError(
            "La hora de inicio debe ser anterior a la hora de fin."
        )
    if target.slot_minutes <= 0 or target.slot_minutes > 480:
        raise ValidationError(
            "La duracion del slot debe estar entre 1 y 480 minutos."
        )
