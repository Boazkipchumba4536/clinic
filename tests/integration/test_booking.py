from datetime import datetime, timedelta

import pytest

from tests.helpers import DERM_ID, GP_ID, NAIROBI, PATIENT_A, PATIENT_B, iso, next_weekday


async def book(client, doctor_id: str, patient_id: str, start: str, expected: int = 201):
    response = await client.post(
        "/appointments",
        json={"doctor_id": doctor_id, "patient_id": patient_id, "start_at": start},
    )
    assert response.status_code == expected, response.text
    return response.json()


@pytest.mark.asyncio
async def test_successful_booking(client) -> None:
    monday = next_weekday(0)
    body = await book(client, GP_ID, PATIENT_A, iso(monday, 10, 0))
    assert body["status"] == "booked"
    assert body["doctor_id"] == GP_ID
    assert body["patient_id"] == PATIENT_A


@pytest.mark.asyncio
async def test_booking_outside_working_hours(client) -> None:
    monday = next_weekday(0)
    body = await book(client, GP_ID, PATIENT_A, iso(monday, 13, 0), expected=422)
    assert body["error"]["code"] == "SLOT_OUTSIDE_WORKING_HOURS"


@pytest.mark.asyncio
async def test_booking_before_clinic_opens(client) -> None:
    monday = next_weekday(0)
    body = await book(client, GP_ID, PATIENT_A, iso(monday, 8, 0), expected=422)
    assert body["error"]["code"] == "SLOT_OUTSIDE_WORKING_HOURS"


@pytest.mark.asyncio
async def test_booking_in_the_past(client) -> None:
    past_monday = next_weekday(0, min_days=3) - timedelta(days=14)
    body = await book(client, GP_ID, PATIENT_A, iso(past_monday, 10, 0), expected=422)
    assert body["error"]["code"] == "APPOINTMENT_IN_PAST"


@pytest.mark.asyncio
async def test_booking_already_occupied_slot(client) -> None:
    monday = next_weekday(0)
    await book(client, GP_ID, PATIENT_A, iso(monday, 10, 0))
    body = await book(client, GP_ID, PATIENT_B, iso(monday, 10, 0), expected=409)
    assert body["error"]["code"] == "APPOINTMENT_SLOT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_invalid_30_minute_slot(client) -> None:
    monday = next_weekday(0)
    body = await book(client, GP_ID, PATIENT_A, iso(monday, 10, 15), expected=422)
    assert body["error"]["code"] == "SLOT_NOT_ALIGNED"


@pytest.mark.asyncio
async def test_unknown_doctor_or_patient(client) -> None:
    monday = next_weekday(0)
    missing = "00000000-0000-4000-8000-000000000099"
    body = await book(client, missing, PATIENT_A, iso(monday, 10, 0), expected=404)
    assert body["error"]["code"] == "DOCTOR_NOT_FOUND"
    body = await book(client, GP_ID, missing, iso(monday, 10, 0), expected=404)
    assert body["error"]["code"] == "PATIENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_booking_too_soon(client) -> None:
    now = datetime.now(NAIROBI)
    if now.minute < 30:
        candidate = now.replace(minute=30, second=0, microsecond=0)
    else:
        candidate = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if candidate <= datetime.now(candidate.tzinfo):
        candidate += timedelta(minutes=30)
    response = await client.post(
        "/appointments",
        json={
            "doctor_id": GP_ID,
            "patient_id": PATIENT_A,
            "start_at": candidate.isoformat(),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] in {"BOOKING_TOO_SOON", "APPOINTMENT_IN_PAST"}


@pytest.mark.asyncio
async def test_naive_datetime_rejected(client) -> None:
    monday = next_weekday(0)
    response = await client.post(
        "/appointments",
        json={
            "doctor_id": GP_ID,
            "patient_id": PATIENT_A,
            "start_at": f"{monday.isoformat()}T10:00:00",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_doctor_not_working_on_tuesday(client) -> None:
    tuesday = next_weekday(1)
    body = await book(client, DERM_ID, PATIENT_A, iso(tuesday, 10, 0), expected=422)
    assert body["error"]["code"] == "DOCTOR_NOT_WORKING"
