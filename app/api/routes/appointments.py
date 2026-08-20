import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_appointment_service, get_settings_dep
from app.core.config import Settings
from app.core.database import get_db
from app.schemas import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentOut,
    AppointmentReschedule,
    ErrorResponse,
)
from app.services.appointment_service import AppointmentService

router = APIRouter(tags=["Appointments"])

ERROR_RESPONSES = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> AppointmentService:
    return get_appointment_service(session, settings)


@router.post(
    "/appointments",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
    summary="Book an appointment slot",
    description=(
        "Books a 30-minute slot for a patient with a doctor. "
        "The slot must be in the future, respect the configured booking notice, "
        "align to clinic local :00/:30, fall within the doctor's working hours, "
        "and not already be booked. Double-booking is rejected by a PostgreSQL "
        "partial unique index even under concurrent requests."
    ),
)
async def book_appointment(
    payload: AppointmentCreate,
    service: Annotated[AppointmentService, Depends(_service)],
) -> AppointmentOut:
    appointment = await service.book(payload.doctor_id, payload.patient_id, payload.start_at)
    return AppointmentOut.model_validate(appointment)


@router.patch(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentOut,
    responses=ERROR_RESPONSES,
    summary="Cancel an appointment",
    description=(
        "Cancels a booked appointment and records a reason. "
        "The row is retained so history is preserved; the partial unique index "
        "no longer covers it, so the slot becomes bookable again."
    ),
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentCancel,
    service: Annotated[AppointmentService, Depends(_service)],
) -> AppointmentOut:
    appointment = await service.cancel(appointment_id, payload.reason)
    return AppointmentOut.model_validate(appointment)


@router.patch(
    "/appointments/{appointment_id}/reschedule",
    response_model=AppointmentOut,
    responses=ERROR_RESPONSES,
    summary="Reschedule an appointment",
    description=(
        "Moves a booked appointment to a new slot. The original slot is freed "
        "and the new slot is validated as a fresh booking, atomically in one "
        "row update so the unique index still prevents collisions."
    ),
)
async def reschedule_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentReschedule,
    service: Annotated[AppointmentService, Depends(_service)],
) -> AppointmentOut:
    appointment = await service.reschedule(appointment_id, payload.start_at)
    return AppointmentOut.model_validate(appointment)
