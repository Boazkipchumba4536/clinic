from datetime import UTC, datetime

import pytest

from tests.helpers import DERM_ID, GP_ID, PATIENT_A, iso, nairobi, next_weekday


def _as_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _availability_url(doctor_id: str) -> str:
    return f"/doctors/{doctor_id}/availability"


@pytest.mark.asyncio
async def test_availability_calculation(client) -> None:
    monday = next_weekday(0)
    response = await client.get(_availability_url(GP_ID), params={"date": monday.isoformat()})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["working"] is True
    assert data["timezone"] == "Africa/Nairobi"
    statuses = {s["status"] for s in data["slots"]}
    assert "available" in statuses

    starts = {_as_utc(s["start_at"]) for s in data["slots"]}
    assert nairobi(monday, 9, 0).astimezone(UTC) in starts
    assert nairobi(monday, 12, 30).astimezone(UTC) in starts
    assert nairobi(monday, 13, 0).astimezone(UTC) not in starts
    assert nairobi(monday, 14, 0).astimezone(UTC) in starts
    assert nairobi(monday, 16, 30).astimezone(UTC) in starts
    assert nairobi(monday, 17, 0).astimezone(UTC) not in starts


@pytest.mark.asyncio
async def test_availability_marks_booked_slots(client) -> None:
    monday = next_weekday(0)
    book = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 10, 0)},
    )
    assert book.status_code == 201, book.text
    response = await client.get(_availability_url(GP_ID), params={"date": monday.isoformat()})
    data = response.json()
    booked = [s for s in data["slots"] if s["status"] == "booked"]
    assert len(booked) == 1
    assert booked[0]["start_at"] == book.json()["start_at"]


@pytest.mark.asyncio
async def test_availability_after_cancellation(client) -> None:
    monday = next_weekday(0)
    booked = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 11, 0)},
    )
    appointment_id = booked.json()["id"]
    cancel = await client.patch(
        f"/appointments/{appointment_id}/cancel",
        json={"reason": "Feeling better"},
    )
    assert cancel.status_code == 200, cancel.text
    response = await client.get(_availability_url(GP_ID), params={"date": monday.isoformat()})
    matches = [s for s in response.json()["slots"] if s["start_at"] == booked.json()["start_at"]]
    assert matches[0]["status"] == "available"


@pytest.mark.asyncio
async def test_availability_after_reschedule(client) -> None:
    monday = next_weekday(0)
    booked = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 9, 0)},
    )
    appointment_id = booked.json()["id"]
    original = booked.json()["start_at"]
    moved = await client.patch(
        f"/appointments/{appointment_id}/reschedule",
        json={"start_at": iso(monday, 15, 0)},
    )
    assert moved.status_code == 200, moved.text
    response = await client.get(_availability_url(GP_ID), params={"date": monday.isoformat()})
    by_start = {s["start_at"]: s["status"] for s in response.json()["slots"]}
    assert by_start[original] == "available"
    assert by_start[moved.json()["start_at"]] == "booked"


@pytest.mark.asyncio
async def test_availability_when_doctor_does_not_work(client) -> None:
    tuesday = next_weekday(1)
    response = await client.get(
        _availability_url(DERM_ID),
        params={"date": tuesday.isoformat()},
    )
    data = response.json()
    assert data["working"] is False
    assert data["slots"] == []


@pytest.mark.asyncio
async def test_availability_unknown_doctor(client) -> None:
    monday = next_weekday(0)
    missing = "00000000-0000-4000-8000-000000000099"
    response = await client.get(
        _availability_url(missing),
        params={"date": monday.isoformat()},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCTOR_NOT_FOUND"
