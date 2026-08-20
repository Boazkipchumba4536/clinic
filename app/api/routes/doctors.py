import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_availability_service, get_settings_dep
from app.core.config import Settings
from app.core.database import get_db
from app.core.exceptions import DoctorNotFound
from app.repositories.doctor_repository import DoctorRepository
from app.schemas import AvailabilityOut, DoctorOut, ErrorResponse
from app.services.availability_service import AvailabilityService

router = APIRouter(tags=["Doctors"])


@router.get(
    "/doctors",
    response_model=list[DoctorOut],
    summary="List active doctors",
    description="Supporting endpoint so clients can discover doctor IDs before booking.",
)
async def list_doctors(session: Annotated[AsyncSession, Depends(get_db)]) -> list[DoctorOut]:
    doctors = await DoctorRepository(session).list_active()
    return [DoctorOut.model_validate(d) for d in doctors]


@router.get(
    "/doctors/{doctor_id}/availability",
    response_model=AvailabilityOut,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="List 30-minute slots for a doctor on a date",
    description=(
        "Returns every 30-minute slot in the doctor's working windows for the "
        "given calendar date in the clinic timezone. Each slot is labelled "
        "`available`, `booked`, `too_soon` (inside the notice window), or `past`. "
        "Cancelled appointments do not occupy a slot. If the doctor does not "
        "work that weekday, `working` is false and `slots` is empty."
    ),
)
async def doctor_availability(
    doctor_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    on_date: Annotated[
        date,
        Query(
            alias="date",
            description="Calendar date in the clinic timezone (YYYY-MM-DD).",
            examples=["2026-08-24"],
        ),
    ],
) -> AvailabilityOut:
    service: AvailabilityService = get_availability_service(session, settings)
    return await service.for_doctor(doctor_id, on_date)


@router.get(
    "/doctors/{doctor_id}",
    response_model=DoctorOut,
    responses={404: {"model": ErrorResponse}},
    summary="Get a doctor",
)
async def get_doctor(
    doctor_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DoctorOut:
    doctor = await DoctorRepository(session).get_active(doctor_id)
    if doctor is None:
        raise DoctorNotFound()
    return DoctorOut.model_validate(doctor)
