from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.exceptions import (
    AppointmentInPast,
    BookingTooSoon,
    NaiveDateTimeRejected,
    SlotNotAligned,
    SlotOutsideWorkingHours,
)
from app.domain.slots import (
    SLOT_DURATION,
    as_utc,
    assert_within_working_hours,
    ensure_aware,
    generate_slots_for_windows,
    is_slot_aligned,
    validate_booking_window,
    validate_slot_alignment,
)

NAIROBI = ZoneInfo("Africa/Nairobi")
WINDOWS = [(time(9, 0), time(13, 0)), (time(14, 0), time(17, 0))]


def test_naive_datetime_rejected() -> None:
    with pytest.raises(NaiveDateTimeRejected):
        ensure_aware(datetime(2026, 8, 24, 9, 0))


def test_alignment_uses_clinic_local_time_not_utc() -> None:
    # 09:00 Nairobi is 06:00 UTC — still aligned in clinic time.
    start = datetime(2026, 8, 24, 9, 0, tzinfo=NAIROBI)
    assert is_slot_aligned(start, "Africa/Nairobi")
    assert as_utc(start).hour == 6


def test_misaligned_slot_rejected() -> None:
    start = datetime(2026, 8, 24, 9, 15, tzinfo=NAIROBI)
    with pytest.raises(SlotNotAligned):
        validate_slot_alignment(start, "Africa/Nairobi")


def test_generate_slots_skips_lunch_and_stops_at_window_end() -> None:
    day = datetime(2026, 8, 24, tzinfo=NAIROBI).date()
    slots = generate_slots_for_windows(day, WINDOWS, "Africa/Nairobi")
    starts = [start.strftime("%H:%M") for start, _end in slots]
    assert "09:00" in starts
    assert "12:30" in starts
    assert "13:00" not in starts
    assert "13:30" not in starts
    assert "14:00" in starts
    assert "16:30" in starts
    assert "17:00" not in starts
    assert all(end - start == SLOT_DURATION for start, end in slots)


def test_slot_inside_working_hours() -> None:
    start = datetime(2026, 8, 24, 10, 0, tzinfo=NAIROBI)
    assert_within_working_hours(start, "Africa/Nairobi", WINDOWS)


def test_lunch_slot_outside_working_hours() -> None:
    start = datetime(2026, 8, 24, 13, 0, tzinfo=NAIROBI)
    with pytest.raises(SlotOutsideWorkingHours):
        assert_within_working_hours(start, "Africa/Nairobi", WINDOWS)


def test_past_and_too_soon_window() -> None:
    now = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
    past = datetime(2026, 8, 24, 7, 0, tzinfo=UTC)
    soon = now + timedelta(minutes=30)
    future = now + timedelta(days=3)

    with pytest.raises(AppointmentInPast):
        validate_booking_window(past, now=now, notice_minutes=60, max_ahead_days=90)

    with pytest.raises(BookingTooSoon):
        validate_booking_window(soon, now=now, notice_minutes=60, max_ahead_days=90)

    validate_booking_window(future, now=now, notice_minutes=60, max_ahead_days=90)
