import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus


class AppointmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, appointment_id: uuid.UUID) -> Appointment | None:
        return await self.session.get(Appointment, appointment_id)

    async def add(self, appointment: Appointment) -> Appointment:
        self.session.add(appointment)
        await self.session.flush()
        await self.session.refresh(appointment)
        return appointment

    async def booked_starts_between(
        self,
        doctor_id: uuid.UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> set[datetime]:
        result = await self.session.scalars(
            select(Appointment.start_at).where(
                Appointment.doctor_id == doctor_id,
                Appointment.status == AppointmentStatus.BOOKED,
                Appointment.start_at >= range_start,
                Appointment.start_at < range_end,
            )
        )
        return {row for row in result.all()}

    async def upcoming_for_patient(
        self,
        patient_id: uuid.UUID,
        now: datetime,
    ) -> list[Appointment]:
        result = await self.session.scalars(
            select(Appointment)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.status == AppointmentStatus.BOOKED,
                Appointment.start_at >= now,
            )
            .order_by(Appointment.start_at.asc())
        )
        return list(result.all())
