"""Pure booking-domain helpers. These have no I/O and are unit-tested directly."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.exceptions import (
    AppointmentInPast,
    BookingTooFarAhead,
    BookingTooSoon,
    DoctorNotWorking,
    NaiveDateTimeRejected,
    SlotNotAligned,
    SlotOutsideWorkingHours,
)

SLOT_DURATION = timedelta(minutes=30)


def clinic_zone(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise NaiveDateTimeRejected()
    return value


def as_utc(value: datetime) -> datetime:
    return ensure_aware(value).astimezone(UTC)


def as_clinic_local(value: datetime, tz_name: str) -> datetime:
    return ensure_aware(value).astimezone(clinic_zone(tz_name))


def is_slot_aligned(start_at: datetime, tz_name: str) -> bool:
    """Slots align to :00 or :30 in clinic local time, not UTC."""
    local = as_clinic_local(start_at, tz_name)
    return local.minute in (0, 30) and local.second == 0 and local.microsecond == 0


def validate_slot_alignment(start_at: datetime, tz_name: str) -> None:
    if not is_slot_aligned(start_at, tz_name):
        raise SlotNotAligned()


def validate_booking_window(
    start_at: datetime,
    *,
    now: datetime,
    notice_minutes: int,
    max_ahead_days: int,
) -> None:
    start_utc = as_utc(start_at)
    now_utc = as_utc(now)

    if start_utc <= now_utc:
        raise AppointmentInPast()

    if start_utc < now_utc + timedelta(minutes=notice_minutes):
        raise BookingTooSoon(notice_minutes)

    if start_utc > now_utc + timedelta(days=max_ahead_days):
        raise BookingTooFarAhead(max_ahead_days)


def slot_end(start_at: datetime) -> datetime:
    return start_at + SLOT_DURATION


def generate_slots_for_windows(
    day: date,
    windows: list[tuple[time, time]],
    tz_name: str,
) -> list[tuple[datetime, datetime]]:
    """Generate 30-minute slots fully contained in the given local-time windows."""
    tz = clinic_zone(tz_name)
    slots: list[tuple[datetime, datetime]] = []
    for start_time, end_time in windows:
        cursor = datetime.combine(day, start_time, tzinfo=tz)
        window_end = datetime.combine(day, end_time, tzinfo=tz)
        while cursor + SLOT_DURATION <= window_end:
            slots.append((cursor, cursor + SLOT_DURATION))
            cursor += SLOT_DURATION
    return slots


def slot_fits_windows(
    start_at: datetime,
    tz_name: str,
    windows: list[tuple[time, time]],
) -> bool:
    local_start = as_clinic_local(start_at, tz_name)
    local_end = local_start + SLOT_DURATION
    local_date = local_start.date()
    if local_end.date() != local_date:
        return False
    start_t = local_start.time()
    end_t = local_end.time()
    return any(
        window_start <= start_t and end_t <= window_end for window_start, window_end in windows
    )


def assert_within_working_hours(
    start_at: datetime,
    tz_name: str,
    windows: list[tuple[time, time]],
) -> None:
    if not windows:
        raise DoctorNotWorking()
    if not slot_fits_windows(start_at, tz_name, windows):
        raise SlotOutsideWorkingHours()
