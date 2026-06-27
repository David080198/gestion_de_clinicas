"""Servicio de agendamiento: citas, colisiones y disponibilidad.

Centraliza las reglas de negocio del modulo de citas:
    - Validacion de franja dentro del horario del medico.
    - Control estricto de colisiones (no dos citas al mismo medico
      solapadas en el tiempo).
    - Transiciones de estado con la maquina de estados definida en enums.
    - Generacion de slots disponibles para una fecha dada.
    - Filtros por medico/paciente/fecha para el calendario y dashboards.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import and_, select

from app.exceptions import (
    AppointmentCollisionError,
    AppointmentStateError,
    AuthorizationError,
    OutOfScheduleError,
    RecordNotFoundError,
    ValidationError,
)
from app.extensions import db
from app.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    DoctorSchedule,
    Patient,
    User,
    UserRole,
    Weekday,
)


class AppointmentService:
    """Logica de negocio del modulo de citas."""

    # ============================================================
    # Creacion
    # ============================================================

    @staticmethod
    def create_appointment(
        payload: dict[str, Any],
        acting_user: User,
    ) -> Appointment:
        """Crea una cita validando colisiones y horario del medico.

        Reglas RBAC:
            - Recepcionista/Admin: pueden agendar para cualquier paciente.
            - Paciente: solo puede agendar para si mismo.
            - Medico: no agenda (solo confirma/atiende).

        Args:
            payload: Datos validados por AppointmentCreateSchema.
            acting_user: Usuario autenticado.

        Returns:
            La cita creada (commit realizado).
        """
        patient_id: int = payload["patient_id"]
        doctor_id: int = payload["doctor_id"]
        start_time: datetime = payload["start_time"]
        end_time: datetime = payload["end_time"]

        # --- Permisos paciente ---
        if acting_user.role == UserRole.PACIENTE:
            if not acting_user.patient_profile:
                raise AuthorizationError("Tu cuenta no tiene perfil de paciente.")
            if patient_id != acting_user.patient_profile.id:
                raise AuthorizationError(
                    "Solo puedes agendar citas para ti mismo."
                )

        # --- Multi-tenancy: verificar que paciente y medico son de la misma clinica ---
        from app.utils.tenant import assert_resource_belongs_to_clinic

        # Usar el clinic_id del usuario que ejecuta la accion (mas confiable que g)
        clinic_id: int | None = acting_user.clinic_id

        # --- Existencia de recursos ---
        patient: Patient | None = db.session.get(Patient, patient_id)
        if patient is None:
            raise RecordNotFoundError(f"Paciente {patient_id} no encontrado.")
        assert_resource_belongs_to_clinic(patient, "paciente")

        doctor: Doctor | None = db.session.get(Doctor, doctor_id)
        if doctor is None:
            raise RecordNotFoundError(f"Medico {doctor_id} no encontrado.")
        assert_resource_belongs_to_clinic(doctor, "medico")

        if not doctor.is_available:
            raise OutOfScheduleError("El medico no recibe nuevas citas.")

        # --- Coherencia temporal ---
        if start_time >= end_time:
            raise ValidationError("La hora de inicio debe ser anterior a la fin.")
        if end_time - start_time > timedelta(hours=8):
            raise ValidationError("La duracion de la cita no puede exceder 8 horas.")
        if start_time < datetime.now(start_time.tzinfo):
            raise ValidationError("No se pueden agendar citas en el pasado.")

        # --- Validacion contra el horario del medico ---
        AppointmentService._assert_within_schedule(doctor, start_time, end_time)

        # --- Control de colisiones ---
        Appointment.assert_no_collision(doctor_id, start_time, end_time)

        # --- Crear cita ---
        receptionist_id: int | None = (
            acting_user.id if acting_user.role in {UserRole.RECEPCIONISTA, UserRole.ADMIN} else None
        )
        initial_status: AppointmentStatus = (
            AppointmentStatus.CONFIRMADA
            if acting_user.role in {UserRole.RECEPCIONISTA, UserRole.ADMIN, UserRole.MEDICO}
            else AppointmentStatus.PENDIENTE  # el paciente solicita, staff confirma
        )

        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            receptionist_id=receptionist_id,
            clinic_id=clinic_id,
            start_time=start_time,
            end_time=end_time,
            status=initial_status,
            reason=payload.get("reason"),
            notes=payload.get("notes"),
        )
        appointment.save()
        return appointment

    # ============================================================
    # Validacion de horario
    # ============================================================

    @staticmethod
    def _assert_within_schedule(
        doctor: Doctor, start_time: datetime, end_time: datetime
    ) -> None:
        """Verifica que la cita caiga dentro de una franja activa del medico.

        Raises:
            OutOfScheduleError: Si no hay franja para ese dia o la cita
                excede los limites de la franja.
        """
        weekday: Weekday = Weekday(start_time.weekday())
        start_t: time = start_time.time()
        end_t: time = end_time.time()

        schedules: list[DoctorSchedule] = list(
            db.session.scalars(
                select(DoctorSchedule).where(
                    DoctorSchedule.doctor_id == doctor.id,
                    DoctorSchedule.weekday == weekday,
                    DoctorSchedule.is_active.is_(True),
                )
            )
        )
        if not schedules:
            raise OutOfScheduleError(
                f"El medico no atiende los {weekday.name.lower()}."
            )
        for sched in schedules:
            if sched.contains(start_t, end_t):
                return
        raise OutOfScheduleError(
            "La cita esta fuera del horario de atencion del medico."
        )

    # ============================================================
    # Disponibilidad (slots libres)
    # ============================================================

    @staticmethod
    def get_available_slots(
        doctor_id: int, day: date, slot_minutes: int = 30
    ) -> list[dict[str, Any]]:
        """Calcula los slots libres para un medico en una fecha.

        Args:
            doctor_id: Medico.
            day: Fecha a consultar.
            slot_minutes: Duracion de cada slot en minutos.

        Returns:
            Lista de slots: [{start, end, available}].
        """
        doctor: Doctor | None = db.session.get(Doctor, doctor_id)
        if doctor is None:
            raise RecordNotFoundError(f"Medico {doctor_id} no encontrado.")

        weekday: Weekday = Weekday(day.weekday())
        schedules: list[DoctorSchedule] = list(
            db.session.scalars(
                select(DoctorSchedule).where(
                    DoctorSchedule.doctor_id == doctor.id,
                    DoctorSchedule.weekday == weekday,
                    DoctorSchedule.is_active.is_(True),
                )
            )
        )
        if not schedules:
            return []

        # Citas ya ocupadas ese dia
        day_start: datetime = datetime.combine(day, time.min)
        day_end: datetime = datetime.combine(day, time.max)
        existing: list[Appointment] = list(
            db.session.scalars(
                select(Appointment).where(
                    Appointment.doctor_id == doctor_id,
                    Appointment.status != AppointmentStatus.CANCELADA,
                    Appointment.start_time < day_end,
                    Appointment.end_time > day_start,
                )
            )
        )

        slots: list[dict[str, Any]] = []
        duration: timedelta = timedelta(minutes=slot_minutes)
        now: datetime = datetime.now()

        for sched in schedules:
            cursor: datetime = datetime.combine(day, sched.start_time)
            sched_end: datetime = datetime.combine(day, sched.end_time)
            while cursor + duration <= sched_end:
                slot_start: datetime = cursor
                slot_end: datetime = cursor + duration
                # Slot en el pasado?
                if slot_end <= now:
                    slots.append(
                        {"start": slot_start.isoformat(), "end": slot_end.isoformat(), "available": False, "reason": "past"}
                    )
                    cursor = slot_end
                    continue
                # Colision con cita existente?
                busy: bool = any(
                    slot_start < e.end_time and slot_end > e.start_time
                    for e in existing
                )
                slots.append(
                    {
                        "start": slot_start.isoformat(),
                        "end": slot_end.isoformat(),
                        "available": not busy,
                        "reason": "busy" if busy else None,
                    }
                )
                cursor = slot_end
        return slots

    # ============================================================
    # Transicion de estado
    # ============================================================

    @staticmethod
    def change_status(
        appointment_id: int, new_status: AppointmentStatus, acting_user: User
    ) -> Appointment:
        """Transita una cita al nuevo estado validando permisos.

        Reglas RBAC:
            - Confirmar una cita pendiente: recepcionista, medico, admin.
            - Pasar a EN_CONSULTA / COMPLETADA: solo el medico asignado o admin.
            - Cancelar: recepcionista, medico asignado, admin, o el propio
              paciente (si no esta completada).
        """
        appointment: Appointment | None = db.session.get(Appointment, appointment_id)
        if appointment is None:
            raise RecordNotFoundError(f"Cita {appointment_id} no encontrada.")

        # --- Permisos segun transicion ---
        AppointmentService._assert_can_change_status(
            appointment, new_status, acting_user
        )

        appointment.transition_to(new_status)
        db.session.commit()
        return appointment

    @staticmethod
    def _assert_can_change_status(
        appointment: Appointment, new_status: AppointmentStatus, user: User
    ) -> None:
        """Valida permisos por transicion y usuario."""
        # Paciente solo puede cancelar
        if user.role == UserRole.PACIENTE:
            if new_status != AppointmentStatus.CANCELADA:
                raise AuthorizationError(
                    "Los pacientes solo pueden cancelar citas."
                )
            if not user.patient_profile or user.patient_profile.id != appointment.patient_id:
                raise AuthorizationError("No puedes modificar citas ajenas.")
            if appointment.status in {
                AppointmentStatus.COMPLETADA,
                AppointmentStatus.CANCELADA,
            }:
                raise AppointmentStateError(
                    "No se puede cancelar una cita completada o ya cancelada."
                )
            return

        # Medico: solo sobre sus propias citas
        if user.role == UserRole.MEDICO:
            if not user.doctor_profile or user.doctor_profile.id != appointment.doctor_id:
                raise AuthorizationError("Solo puedes modificar tus propias citas.")

        # Recepcionista: puede confirmar/cancelar, pero no pasar a EN_CONSULTA/COMPLETADA
        if user.role == UserRole.RECEPCIONISTA and new_status in {
            AppointmentStatus.EN_CONSULTA,
            AppointmentStatus.COMPLETADA,
        }:
            raise AuthorizationError(
                "Solo el medico puede iniciar o completar una consulta."
            )

    # ============================================================
    # Reprogramar
    # ============================================================

    @staticmethod
    def reschedule(
        appointment_id: int,
        new_start: datetime,
        new_end: datetime,
        acting_user: User,
    ) -> Appointment:
        """Reprograma una cita validando nuevo horario y colisiones.

        Solo permitido mientras la cita no este EN_CONSULTA o COMPLETADA.
        """
        appointment: Appointment | None = db.session.get(Appointment, appointment_id)
        if appointment is None:
            raise RecordNotFoundError(f"Cita {appointment_id} no encontrada.")

        if appointment.status in {
            AppointmentStatus.EN_CONSULTA,
            AppointmentStatus.COMPLETADA,
            AppointmentStatus.CANCELADA,
        }:
            raise AppointmentStateError(
                "No se puede reprogramar una cita en curso, completada o cancelada."
            )

        # Permisos paciente
        if acting_user.role == UserRole.PACIENTE:
            if not acting_user.patient_profile or acting_user.patient_profile.id != appointment.patient_id:
                raise AuthorizationError("Solo puedes reprogramar tus propias citas.")

        if new_start >= new_end:
            raise ValidationError("La hora de inicio debe ser anterior a la fin.")
        if new_start < datetime.now(new_start.tzinfo):
            raise ValidationError("No se pueden reprogramar al pasado.")

        doctor: Doctor | None = db.session.get(Doctor, appointment.doctor_id)
        assert doctor is not None
        AppointmentService._assert_within_schedule(doctor, new_start, new_end)
        Appointment.assert_no_collision(
            appointment.doctor_id, new_start, new_end, exclude_id=appointment.id
        )

        appointment.start_time = new_start
        appointment.end_time = new_end
        # al reprogramar vuelve a pendiente si no estaba confirmada por staff
        db.session.commit()
        return appointment

    # ============================================================
    # Consultas / listados
    # ============================================================

    @staticmethod
    def get_appointment_or_404(appointment_id: int) -> Appointment:
        appointment: Appointment | None = db.session.get(Appointment, appointment_id)
        if appointment is None:
            raise RecordNotFoundError(f"Cita {appointment_id} no encontrada.")
        return appointment

    @staticmethod
    def list_appointments(
        acting_user: User,
        doctor_id: int | None = None,
        patient_id: int | None = None,
        status: AppointmentStatus | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Appointment], dict[str, Any]]:
        """Lista citas paginadas con filtros y scope por rol.

        - Paciente: solo sus citas.
        - Medico: solo sus citas.
        - Recepcionista/Admin: todas, con filtros opcionales.
        """
        stmt = select(Appointment)
        # Multi-tenancy: filtrar por clinic_id (super-admin ve todas)
        if acting_user.clinic_id is not None:
            stmt = stmt.where(Appointment.clinic_id == acting_user.clinic_id)

        if acting_user.role == UserRole.PACIENTE:
            if not acting_user.patient_profile:
                return [], {"page": 1, "per_page": per_page, "total": 0, "pages": 0}
            stmt = stmt.where(Appointment.patient_id == acting_user.patient_profile.id)
        elif acting_user.role == UserRole.MEDICO:
            if not acting_user.doctor_profile:
                return [], {"page": 1, "per_page": per_page, "total": 0, "pages": 0}
            stmt = stmt.where(Appointment.doctor_id == acting_user.doctor_profile.id)

        if doctor_id is not None:
            stmt = stmt.where(Appointment.doctor_id == doctor_id)
        if patient_id is not None:
            stmt = stmt.where(Appointment.patient_id == patient_id)
        if status is not None:
            stmt = stmt.where(Appointment.status == status)
        if start is not None:
            stmt = stmt.where(Appointment.start_time >= start)
        if end is not None:
            stmt = stmt.where(Appointment.start_time <= end)

        stmt = stmt.order_by(Appointment.start_time.asc())
        pagination = db.paginate(stmt, page=page, per_page=per_page)
        return list(pagination), {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        }

    @staticmethod
    def list_calendar(
        acting_user: User, start: date, end: date
    ) -> list[Appointment]:
        """Retorna todas las citas en el rango [start, end] segun el rol."""
        start_dt: datetime = datetime.combine(start, time.min)
        end_dt: datetime = datetime.combine(end, time.max)

        stmt = select(Appointment).where(
            Appointment.start_time >= start_dt,
            Appointment.start_time <= end_dt,
            Appointment.status != AppointmentStatus.CANCELADA,
        )
        if acting_user.role == UserRole.MEDICO and acting_user.doctor_profile:
            stmt = stmt.where(Appointment.doctor_id == acting_user.doctor_profile.id)
        elif acting_user.role == UserRole.PACIENTE and acting_user.patient_profile:
            stmt = stmt.where(Appointment.patient_id == acting_user.patient_profile.id)

        stmt = stmt.order_by(Appointment.start_time.asc())
        return list(db.session.scalars(stmt))
