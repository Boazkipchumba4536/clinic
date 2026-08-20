import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_appointment_service, get_settings_dep
from app.core.config import Settings
from app.core.database import get_db
from app.core.exceptions import PatientNotFound
from app.repositories.patient_repository import PatientRepository
from app.schemas import AppointmentOut, ErrorResponse, PatientOut
from app.services.appointment_service import AppointmentService

router = APIRouter(tags=["Patients"])


@router.get(
    "/patients",
    response_model=list[PatientOut],
    summary="List active patients",
    description="Supporting endpoint so clients can discover patient IDs before booking.",
)
async def list_patients(session: Annotated[AsyncSession, Depends(get_db)]) -> list[PatientOut]:
    patients = await PatientRepository(session).list_active()
    return [PatientOut.model_validate(p) for p in patients]


@router.get(
    "/patients/{patient_id}",
    response_model=PatientOut,
    responses={404: {"model": ErrorResponse}},
    summary="Get a patient",
)
async def get_patient(
    patient_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PatientOut:
    patient = await PatientRepository(session).get_active(patient_id)
    if patient is None:
        raise PatientNotFound()
    return PatientOut.model_validate(patient)


@router.get(
    "/patients/{patient_id}/appointments",
    response_model=list[AppointmentOut],
    responses={404: {"model": ErrorResponse}},
    summary="Upcoming appointments for a patient",
    description=(
        "Returns booked appointments whose start time is still in the future, "
        "sorted by start time. Cancelled appointments are excluded."
    ),
)
async def patient_appointments(
    patient_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> list[AppointmentOut]:
    service: AppointmentService = get_appointment_service(session, settings)
    appointments = await service.upcoming_for_patient(patient_id)
    return [AppointmentOut.model_validate(a) for a in appointments]
