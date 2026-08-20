import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient


class PatientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, patient_id: uuid.UUID) -> Patient | None:
        return await self.session.get(Patient, patient_id)

    async def get_active(self, patient_id: uuid.UUID) -> Patient | None:
        patient = await self.get(patient_id)
        if patient is None or not patient.is_active:
            return None
        return patient

    async def list_active(self) -> list[Patient]:
        result = await self.session.scalars(
            select(Patient).where(Patient.is_active.is_(True)).order_by(Patient.full_name)
        )
        return list(result.all())
