import asyncio

import pytest

from tests.helpers import GP_ID, PATIENT_A, PATIENT_B, PATIENT_C, iso, next_weekday


@pytest.mark.asyncio
async def test_patient_upcoming_appointments_sorted_and_excludes_cancelled(client) -> None:
    monday = next_weekday(0)
    tuesday = next_weekday(2)  # Wednesday, still a working day for GP
    first = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(tuesday, 10, 0)},
    )
    second = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 9, 0)},
    )
    cancelled = await client.post(
        "/appointments",
        json={"doctor_id": GP_ID, "patient_id": PATIENT_A, "start_at": iso(monday, 9, 30)},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    await client.patch(
        f"/appointments/{cancelled.json()['id']}/cancel",
        json={"reason": "No longer needed"},
    )

    response = await client.get(f"/patients/{PATIENT_A}/appointments")
    assert response.status_code == 200, response.text
    items = response.json()
    ids = [row["id"] for row in items]
    assert cancelled.json()["id"] not in ids
    starts = [row["start_at"] for row in items]
    assert starts == sorted(starts)
    assert second.json()["id"] in ids
    assert first.json()["id"] in ids


@pytest.mark.asyncio
async def test_patient_appointments_unknown_patient(client) -> None:
    missing = "00000000-0000-4000-8000-000000000099"
    response = await client.get(f"/patients/{missing}/appointments")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PATIENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_concurrent_double_booking(client) -> None:
    monday = next_weekday(0)
    payload_a = {"doctor_id": GP_ID, "patient_id": PATIENT_B, "start_at": iso(monday, 15, 30)}
    payload_b = {"doctor_id": GP_ID, "patient_id": PATIENT_C, "start_at": iso(monday, 15, 30)}

    first, second = await asyncio.gather(
        client.post("/appointments", json=payload_a),
        client.post("/appointments", json=payload_b),
    )
    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [201, 409], (
        f"{first.status_code}: {first.text} | {second.status_code}: {second.text}"
    )
    conflict = first if first.status_code == 409 else second
    assert conflict.json()["error"]["code"] == "APPOINTMENT_SLOT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_health(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "up"
