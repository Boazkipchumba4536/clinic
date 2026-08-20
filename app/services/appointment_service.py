import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    AppointmentAlreadyCancelled,
    AppointmentInPast,
    AppointmentIsCancelled,
    AppointmentNotFound,
    DoctorNotFound,
    PatientNotFound,
    SlotUnavailable,
)
from app.domain.slots import (
    as_clinic_local,
    as_utc,
    assert_within_working_hours,
    slot_end,
    validate_booking_window,
    validate_slot_alignment,
)
from app.models.appointment import Appointment, AppointmentStatus
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.patient_repository import PatientRepository

logger = logging.getLogger(__name__)


class AppointmentService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.appointments = AppointmentRepository(session)
        self.doctors = DoctorRepository(session)
        self.patients = PatientRepository(session)

    def _now(self) -> datetime:
        return datetime.now(UTC)

    async def _require_doctor(self, doctor_id: uuid.UUID):
        doctor = await self.doctors.get_active(doctor_id)
        if doctor is None:
            raise DoctorNotFound()
        return doctor

    async def _require_patient(self, patient_id: uuid.UUID):
        patient = await self.patients.get_active(patient_id)
        if patient is None:
            raise PatientNotFound()
        return patient

    async def _require_appointment(self, appointment_id: uuid.UUID) -> Appointment:
        appointment = await self.appointments.get(appointment_id)
        if appointment is None:
            raise AppointmentNotFound()
        return appointment

    async def _assert_working_hours(self, doctor_id: uuid.UUID, start_at: datetime) -> None:
        local = as_clinic_local(start_at, self.settings.clinic_timezone)
        windows = await self.doctors.windows_for_weekday(doctor_id, local.weekday())
        assert_within_working_hours(start_at, self.settings.clinic_timezone, windows)

    def _validate_new_slot(self, start_at: datetime) -> datetime:
        validate_slot_alignment(start_at, self.settings.clinic_timezone)
        validate_booking_window(
            start_at,
            now=self._now(),
            notice_minutes=self.settings.min_booking_notice_minutes,
            max_ahead_days=self.settings.max_booking_ahead_days,
        )
        return as_utc(start_at)

    async def book(
        self,
        doctor_id: uuid.UUID,
        patient_id: uuid.UUID,
        start_at: datetime,
    ) -> Appointment:
        start_utc = self._validate_new_slot(start_at)
        await self._require_doctor(doctor_id)
        await self._require_patient(patient_id)
        await self._assert_working_hours(doctor_id, start_utc)

        appointment = Appointment(
            doctor_id=doctor_id,
            patient_id=patient_id,
            start_at=start_utc,
            end_at=slot_end(start_utc),
            status=AppointmentStatus.BOOKED,
        )
        return await self._persist_slot_change(appointment)

    async def cancel(self, appointment_id: uuid.UUID, reason: str) -> Appointment:
        appointment = await self._require_appointment(appointment_id)
        if appointment.status == AppointmentStatus.CANCELLED:
            raise AppointmentAlreadyCancelled()
        if appointment.start_at <= self._now():
            raise AppointmentInPast()

        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancellation_reason = reason.strip()
        appointment.cancelled_at = self._now()
        await self.session.flush()
        await self.session.refresh(appointment)
        return appointment

    async def reschedule(self, appointment_id: uuid.UUID, start_at: datetime) -> Appointment:
        appointment = await self._require_appointment(appointment_id)
        if appointment.status == AppointmentStatus.CANCELLED:
            raise AppointmentIsCancelled()
        if appointment.start_at <= self._now():
            raise AppointmentInPast()

        start_utc = self._validate_new_slot(start_at)
        await self._assert_working_hours(appointment.doctor_id, start_utc)

        if start_utc == appointment.start_at:
            return appointment

        appointment.start_at = start_utc
        appointment.end_at = slot_end(start_utc)
        return await self._persist_slot_change(appointment)

    async def upcoming_for_patient(self, patient_id: uuid.UUID) -> list[Appointment]:
        await self._require_patient(patient_id)
        return await self.appointments.upcoming_for_patient(patient_id, self._now())

    async def _persist_slot_change(self, appointment: Appointment) -> Appointment:
        """Flush and translate the partial unique index into a 409.

        Two concurrent bookings of the same (doctor, start_at) both pass the
        application-level working-hours checks. PostgreSQL then serializes
        the inserts/updates: exactly one transaction commits; the other hits
        uq_appointments_doctor_slot_booked and becomes SlotUnavailable.
        """
        self.session.add(appointment)
        try:
            await self.session.flush()
            await self.session.refresh(appointment)
            return appointment
        except IntegrityError as exc:
            orig = str(getattr(exc, "orig", exc))
            if "uq_appointments_doctor_slot_booked" in orig:
                logger.info("Rejected concurrent or duplicate booking via unique index")
                raise SlotUnavailable() from exc
            raise
