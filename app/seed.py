"""Idempotent sample data: 5 doctors, weekday windows, and 5 patients."""

import asyncio
import uuid
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.schedule import DoctorSchedule

DOCTORS = [
    {
        "id": uuid.UUID("550e8400-e29b-41d4-a716-446655440001"),
        "full_name": "Dr. Amina Odhiambo",
        "specialty": "General Practice",
        "weekdays": [0, 1, 2, 3, 4],
        "saturday": False,
    },
    {
        "id": uuid.UUID("550e8400-e29b-41d4-a716-446655440002"),
        "full_name": "Dr. James Mwangi",
        "specialty": "Pediatrics",
        "weekdays": [0, 1, 2, 3, 4],
        "saturday": True,
    },
    {
        "id": uuid.UUID("550e8400-e29b-41d4-a716-446655440003"),
        "full_name": "Dr. Wanjiku Njoroge",
        "specialty": "Dermatology",
        "weekdays": [0, 2, 3, 4],  # Tuesday off
        "saturday": False,
    },
    {
        "id": uuid.UUID("550e8400-e29b-41d4-a716-446655440004"),
        "full_name": "Dr. Samuel Otieno",
        "specialty": "Internal Medicine",
        "weekdays": [0, 1, 2, 3, 4],
        "saturday": False,
    },
    {
        "id": uuid.UUID("550e8400-e29b-41d4-a716-446655440005"),
        "full_name": "Dr. Faith Wambui",
        "specialty": "Obstetrics",
        "weekdays": [0, 1, 2, 3, 4],
        "saturday": False,
    },
]

WEEKDAY_WINDOWS = [
    (time(9, 0), time(13, 0)),
    (time(14, 0), time(17, 0)),
]
SATURDAY_WINDOWS = [
    (time(9, 0), time(13, 0)),
]

PATIENTS = [
    {
        "id": uuid.UUID("660e8400-e29b-41d4-a716-446655440001"),
        "full_name": "Grace Njeri",
        "email": "grace.njeri@example.com",
        "phone": "+254700000001",
    },
    {
        "id": uuid.UUID("660e8400-e29b-41d4-a716-446655440002"),
        "full_name": "Peter Kamau",
        "email": "peter.kamau@example.com",
        "phone": "+254700000002",
    },
    {
        "id": uuid.UUID("660e8400-e29b-41d4-a716-446655440003"),
        "full_name": "Lucy Achieng",
        "email": "lucy.achieng@example.com",
        "phone": "+254700000003",
    },
    {
        "id": uuid.UUID("660e8400-e29b-41d4-a716-446655440004"),
        "full_name": "Daniel Kipchoge",
        "email": "daniel.kipchoge@example.com",
        "phone": "+254700000004",
    },
    {
        "id": uuid.UUID("660e8400-e29b-41d4-a716-446655440005"),
        "full_name": "Mary Wairimu",
        "email": "mary.wairimu@example.com",
        "phone": "+254700000005",
    },
]


async def seed(session: AsyncSession) -> None:
    for spec in DOCTORS:
        existing = await session.get(Doctor, spec["id"])
        if existing is None:
            session.add(
                Doctor(
                    id=spec["id"],
                    full_name=spec["full_name"],
                    specialty=spec["specialty"],
                    is_active=True,
                )
            )
            await session.flush()

        result = await session.scalars(
            select(DoctorSchedule).where(DoctorSchedule.doctor_id == spec["id"])
        )
        if result.first() is None:
            for weekday in spec["weekdays"]:
                for start_time, end_time in WEEKDAY_WINDOWS:
                    session.add(
                        DoctorSchedule(
                            doctor_id=spec["id"],
                            weekday=weekday,
                            start_time=start_time,
                            end_time=end_time,
                        )
                    )
            if spec["saturday"]:
                for start_time, end_time in SATURDAY_WINDOWS:
                    session.add(
                        DoctorSchedule(
                            doctor_id=spec["id"],
                            weekday=5,
                            start_time=start_time,
                            end_time=end_time,
                        )
                    )

    for spec in PATIENTS:
        if await session.get(Patient, spec["id"]) is None:
            session.add(Patient(**spec, is_active=True))

    await session.flush()


async def _run() -> None:
    async with SessionLocal() as session:
        await seed(session)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(_run())
