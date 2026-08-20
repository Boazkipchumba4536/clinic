import pytest

from tests.helpers import GP_ID, PATIENT_A, PATIENT_B, iso, next_weekday


@pytest.mark.asyncio
async def test_cancel_appointment(client) -> None:
    monday = next_weekday(0)
    booked = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 10, 0)},
    )
    appointment_id = booked.json()["id"]
    response = await client.patch(
        f"/appointments/{appointment_id}/cancel",
        json={"reason": "Schedule conflict"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["cancellation_reason"] == "Schedule conflict"
    assert body["cancelled_at"] is not None


@pytest.mark.asyncio
async def test_cancel_already_cancelled(client) -> None:
    monday = next_weekday(0)
    booked = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 10, 30)},
    )
    appointment_id = booked.json()["id"]
    await client.patch(
        f"/appointments/{appointment_id}/cancel",
        json={"reason": "First cancel"},
    )
    response = await client.patch(
        f"/appointments/{appointment_id}/cancel",
        json={"reason": "Second cancel"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "APPOINTMENT_ALREADY_CANCELLED"


@pytest.mark.asyncio
async def test_reschedule_appointment(client) -> None:
    monday = next_weekday(0)
    booked = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 9, 0)},
    )
    appointment_id = booked.json()["id"]
    response = await client.patch(
        f"/appointments/{appointment_id}/reschedule",
        json={"start_at": iso(monday, 16, 0)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["start_at"] != booked.json()["start_at"]


@pytest.mark.asyncio
async def test_reschedule_to_occupied_slot(client) -> None:
    monday = next_weekday(0)
    first = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 9, 30)},
    )
    occupied = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_B, "start_at": iso(monday, 11, 0)},
    )
    assert occupied.status_code == 201, occupied.text
    response = await client.patch(
        f"/appointments/{first.json()['id']}/reschedule",
        json={"start_at": iso(monday, 11, 0)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "APPOINTMENT_SLOT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_reschedule_cancelled_appointment(client) -> None:
    monday = next_weekday(0)
    booked = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 14, 0)},
    )
    appointment_id = booked.json()["id"]
    await client.patch(
        f"/appointments/{appointment_id}/cancel",
        json={"reason": "Cannot attend"},
    )
    response = await client.patch(
        f"/appointments/{appointment_id}/reschedule",
        json={"start_at": iso(monday, 15, 0)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "APPOINTMENT_CANCELLED"


@pytest.mark.asyncio
async def test_cancel_missing_reason_is_validation_error(client) -> None:
    monday = next_weekday(0)
    booked = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 16, 30)},
    )
    response = await client.patch(
        f"/appointments/{booked.json()['id']}/cancel",
        json={"reason": ""},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_slot_is_bookable_again_after_cancel(client) -> None:
    monday = next_weekday(0)
    first = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 15, 30)},
    )
    assert first.status_code == 201, first.text
    cancel = await client.patch(
        f"/appointments/{first.json()['id']}/cancel",
        json={"reason": "Freeing the slot"},
    )
    assert cancel.status_code == 200, cancel.text
    second = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_B, "start_at": iso(monday, 15, 30)},
    )
    assert second.status_code == 201, second.text
    assert second.json()["status"] == "booked"


@pytest.mark.asyncio
async def test_original_slot_is_bookable_after_reschedule(client) -> None:
    monday = next_weekday(0)
    first = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 14, 30)},
    )
    assert first.status_code == 201, first.text
    moved = await client.patch(
        f"/appointments/{first.json()['id']}/reschedule",
        json={"start_at": iso(monday, 16, 30)},
    )
    assert moved.status_code == 200, moved.text
    second = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_B, "start_at": iso(monday, 14, 30)},
    )
    assert second.status_code == 201, second.text


@pytest.mark.asyncio
async def test_reschedule_outside_working_hours(client) -> None:
    monday = next_weekday(0)
    booked = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 9, 0)},
    )
    assert booked.status_code == 201, booked.text
    response = await client.patch(
        f"/appointments/{booked.json()['id']}/reschedule",
        json={"start_at": iso(monday, 13, 0)},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SLOT_OUTSIDE_WORKING_HOURS"
