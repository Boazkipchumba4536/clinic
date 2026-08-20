import uuid
from datetime import date, datetime, time

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.models.appointment import AppointmentStatus


class DoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    specialty: str
    is_active: bool


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    phone: str | None
    is_active: bool


class ScheduleWindowOut(BaseModel):
    weekday: int = Field(description="0 = Monday ... 6 = Sunday")
    start_time: time
    end_time: time


class AppointmentCreate(BaseModel):
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    start_at: AwareDatetime = Field(
        description="Timezone-aware start instant. Must align to a 30-minute clinic slot.",
        examples=["2026-08-24T09:00:00+03:00"],
    )


class AppointmentCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=500, examples=["Patient recovered"])


class AppointmentReschedule(BaseModel):
    start_at: AwareDatetime = Field(
        description="New timezone-aware start instant.",
        examples=["2026-08-24T10:30:00+03:00"],
    )


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    cancellation_reason: str | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SlotOut(BaseModel):
    start_at: datetime
    end_at: datetime
    status: str = Field(description="available | booked | too_soon | past")


class AvailabilityOut(BaseModel):
    doctor_id: uuid.UUID
    date: date
    timezone: str
    working: bool
    slots: list[SlotOut]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthOut(BaseModel):
    status: str
    timezone: str
    database: str
