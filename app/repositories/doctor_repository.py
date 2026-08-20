import uuid
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule


class DoctorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, doctor_id: uuid.UUID) -> Doctor | None:
        return await self.session.get(Doctor, doctor_id)

    async def get_active(self, doctor_id: uuid.UUID) -> Doctor | None:
        doctor = await self.get(doctor_id)
        if doctor is None or not doctor.is_active:
            return None
        return doctor

    async def list_active(self) -> list[Doctor]:
        result = await self.session.scalars(
            select(Doctor).where(Doctor.is_active.is_(True)).order_by(Doctor.full_name)
        )
        return list(result.all())

    async def windows_for_weekday(
        self, doctor_id: uuid.UUID, weekday: int
    ) -> list[tuple[time, time]]:
        result = await self.session.scalars(
            select(DoctorSchedule)
            .where(DoctorSchedule.doctor_id == doctor_id, DoctorSchedule.weekday == weekday)
            .order_by(DoctorSchedule.start_time)
        )
        return [(row.start_time, row.end_time) for row in result.all()]
