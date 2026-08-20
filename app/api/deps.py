from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.services.appointment_service import AppointmentService
from app.services.availability_service import AvailabilityService


def get_settings_dep() -> Settings:
    return get_settings()


def get_appointment_service(session: AsyncSession, settings: Settings) -> AppointmentService:
    return AppointmentService(session, settings)


def get_availability_service(session: AsyncSession, settings: Settings) -> AvailabilityService:
    return AvailabilityService(session, settings)
