import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import DoctorNotFound
from app.domain.slots import as_utc, clinic_zone, generate_slots_for_windows
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.doctor_repository import DoctorRepository
from app.schemas import AvailabilityOut, SlotOut


class AvailabilityService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.doctors = DoctorRepository(session)
        self.appointments = AppointmentRepository(session)

    async def for_doctor(self, doctor_id: uuid.UUID, day: date) -> AvailabilityOut:
        doctor = await self.doctors.get_active(doctor_id)
        if doctor is None:
            raise DoctorNotFound()

        tz_name = self.settings.clinic_timezone
        tz = clinic_zone(tz_name)
        windows = await self.doctors.windows_for_weekday(doctor_id, day.weekday())
        generated = generate_slots_for_windows(day, windows, tz_name)

        day_start = datetime.combine(day, datetime.min.time(), tzinfo=tz)
        day_end = day_start + timedelta(days=1)
        booked = await self.appointments.booked_starts_between(
            doctor_id, as_utc(day_start), as_utc(day_end)
        )
        booked_utc = {as_utc(value) for value in booked}

        now = datetime.now(UTC)
        too_soon_after = now + timedelta(minutes=self.settings.min_booking_notice_minutes)

        slots: list[SlotOut] = []
        for start, end in generated:
            start_utc = as_utc(start)
            if start_utc in booked_utc:
                status = "booked"
            elif start_utc <= now:
                status = "past"
            elif start_utc < too_soon_after:
                status = "too_soon"
            else:
                status = "available"
            slots.append(SlotOut(start_at=start_utc, end_at=as_utc(end), status=status))

        return AvailabilityOut(
            doctor_id=doctor.id,
            date=day,
            timezone=tz_name,
            working=bool(windows),
            slots=slots,
        )
