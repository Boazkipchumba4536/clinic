# Clinic Booking API

REST API for a small clinic (5 doctors today, more later) where patients view 30-minute slots, book, cancel, and reschedule. Double-booking is prevented by PostgreSQL, not by hope.

- **Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x (async), Alembic, PostgreSQL 16, Docker, GitHub Actions
- **Interactive docs:** `/docs` (Swagger) and `/redoc`
- **Health:** `GET /health`

**Public URL:** not deployed from this workspace. Follow [Deployment](#9-deployment) after you build and push, then put the URL here.

**Submission checklist**

1. Create a GitHub repo, commit, push `main`.
2. Confirm Actions → `CI` is green on the first push.
3. Deploy on Render (`render.yaml` or Docker web service + Postgres).
4. Open `GET /health` and `/docs` in a browser.
5. Add GitHub secret `RENDER_DEPLOY_HOOK` so merges to `main` auto-deploy.
6. Paste the public URL at the top of this README.

**Assessment coverage**

| Section | Status |
| --- | --- |
| 1. System design (models, components, decisions, trade-offs) | `README.md` §2–4, 11–12 |
| 2. `POST /appointments` | Implemented + tests |
| 2. `GET /doctors/{id}/availability` | Implemented + tests |
| 2. `PATCH /appointments/{id}/cancel` (reason, already-cancelled, slot freed) | Implemented + tests including re-book |
| 2. `PATCH /appointments/{id}/reschedule` | Implemented + tests |
| 2. Structured code, errors with HTTP codes | `app/api`, `app/services`, `app/domain` |
| 2. Booking tests | `tests/unit`, `tests/integration` |
| 2. Bonus patient list + 1-hour notice | Implemented, configurable |
| 3. Public URL | Fill in after Render is live |
| 3. CI on every PR | `.github/workflows/ci.yml` |
| 3. Auto-deploy on merge to `main` | `.github/workflows/deploy.yml` |
| 4. AI reflection | `AI_REFLECTION.md` |

---

## 1. Project overview

Patients need to see which 30-minute slots a doctor has free on a given day, book one, and later cancel or move it. A booked slot must never be given to a second patient, including when two requests arrive at the same instant.

This repository is the API, database schema, tests, container setup, and CI/CD for that problem. There is no patient-facing UI; `/docs` is the client.

---

## 2. Architecture

```mermaid
flowchart TD
    Client["Client / OpenAPI /docs"] --> API["FastAPI routes"]
    API --> Services["Services: booking + availability"]
    Services --> Domain["Pure domain rules: slots, lead time, alignment"]
    Services --> Repos["Repositories"]
    Repos --> PG["PostgreSQL"]
    PG --> UQ["Partial unique index: one booked row per doctor + start_at"]
```

| Layer | Responsibility |
| --- | --- |
| `app/api/routes` | HTTP status codes, request/response schemas, OpenAPI text |
| `app/services` | Booking lifecycle, availability assembly, transaction-facing writes |
| `app/domain` | Pure functions: 30-minute alignment, working windows, lead time |
| `app/repositories` | SQLAlchemy queries; no business rules |
| `app/models` | Schema, FKs, check constraints, partial unique index |

Routes do not contain booking rules. Domain helpers have no I/O, so they are unit-tested without PostgreSQL.

---

## 3. System design

### Entities

| Entity | Role |
| --- | --- |
| **Doctor** | Clinician who owns a diary. `is_active` supports growth without deleting history. |
| **Patient** | Person who books. Identified by UUID in request bodies (no auth). |
| **DoctorSchedule** | One working-hour *window* on one weekday, in clinic local time. Multiple rows per day model a lunch break. |
| **Appointment** | A 30-minute hold. Rows are never deleted; cancellation changes `status`. |

No extra entities. An audit/event table would help a real clinic; it would not help this assessment.

**Weekday convention:** `0 = Monday` … `6 = Sunday` (Python `date.weekday()`).

**Sample schedules**

- Most doctors: Monday–Friday `09:00–13:00` and `14:00–17:00` (Nairobi time)
- Dr. James Mwangi: also Saturday mornings
- Dr. Wanjiku Njoroge: Tuesday off — used to prove “does not work that day”

### Relationships

- Doctor 1—* DoctorSchedule
- Doctor 1—* Appointment
- Patient 1—* Appointment

### Booking flow

1. Reject naive datetimes; require a timezone offset.
2. Align start time to `:00` or `:30` **in clinic local time**.
3. Reject past, too-soon (configurable lead time), and too-far-ahead starts.
4. Confirm doctor and patient exist and are active.
5. Confirm the slot sits entirely inside a working window for that local weekday.
6. Insert `status = booked`. If the partial unique index fires, return `409 APPOINTMENT_SLOT_UNAVAILABLE`.

### Availability flow

For `GET /doctors/{id}/availability?date=YYYY-MM-DD`:

1. Interpret `date` as a calendar day in `CLINIC_TIMEZONE`.
2. Load that weekday’s windows; if none, `working: false` and `slots: []`.
3. Generate every 30-minute slot fully inside those windows.
4. Load **booked** appointments that day (cancelled rows do not occupy a slot).
5. Label each slot `available`, `booked`, `too_soon`, or `past`.

### Cancellation flow

`PATCH /appointments/{id}/cancel` with a non-empty `reason`. Already-cancelled → `409`. Past appointments → `422`. The row stays; `status` becomes `cancelled`, which drops it from the unique index so the slot can be booked again.

### Reschedule flow

`PATCH /appointments/{id}/reschedule` updates the **same row** to the new `start_at` / `end_at`. The original slot is freed and the new slot is claimed in one statement, so the unique index still serializes races. Cancelled appointments cannot be rescheduled.

**Assumption:** reschedule stays with the same doctor. Moving between doctors is a cancel + book and is left for later.

### Concurrency strategy

Application checks are for *clear errors* (wrong hours, past, unknown doctor). They are **not** the lock.

PostgreSQL enforces:

```sql
CREATE UNIQUE INDEX uq_appointments_doctor_slot_booked
ON appointments (doctor_id, start_at)
WHERE status = 'booked';
```

Two concurrent inserts of the same `(doctor_id, start_at)` with `status = booked`: one commits, the other receives `IntegrityError`, mapped to `409`. Isolation level is default `READ COMMITTED`; the unique index is sufficient. Redis was not added.

Reschedule is an `UPDATE` of the same unique key; a clash with another booked row fails the same way.

---

## 4. Design decisions

| Decision | Reason | Alternative | Trade-off |
| --- | --- | --- | --- |
| Layered FastAPI app, not hexagonal ports/adapters | Assessment size; extra ports would add files without adding correctness | Modular monolith by bounded context; full hexagonal | Slightly less isolation if the app grows into billing/EMR |
| PostgreSQL partial unique index as source of truth | Survives races and app bugs; cancelled rows can coexist with a new booking of the same slot | `SELECT FOR UPDATE` on a slot table; Redis lock; unique on `(doctor_id, start_at)` without `WHERE` | Relies on PostgreSQL (acceptable; we already chose PG) |
| Store instants in UTC (`timestamptz`); interpret hours in `Africa/Nairobi` | Kenya clinic today; UTC in the database stays correct when a second timezone appears | Store Nairobi-naive timestamps | Clients must send offsets; we reject naive datetimes |
| Working hours as weekday windows, not a generated slot table | 5 doctors, 30-minute grid; generating slots on read is cheap and stays correct when hours change | Materialized `slots` table | Recurring exceptions (public holidays) are not modeled |
| Cancel = status change, not delete | Required history; unique index only covers `booked` | Soft-delete flag plus unique | Cancelled duplicates of the same slot can exist; that is intended |
| Reschedule = in-place update | One atomic uniqueness check; original slot frees automatically | Insert new + cancel old | Prior start time is not kept as a revision (documented limitation) |
| Auth out of scope | Brief never asked for login; fake auth would hide the booking design | API keys or JWT | Anyone who knows UUIDs can book/cancel; fine for the take-home, not for production |
| No Redis | Uniqueness belongs in the database | Cache availability in Redis | Availability is always a small per-day read |
| Configurable lead time (`MIN_BOOKING_NOTICE_MINUTES`) | Bonus “no booking within 1 hour” without scattering `60` through the code | Hardcoded 60 | Operators can set `0` in a test environment |
| Render + Docker | Postgres + public URL + deploy hook with almost no cloud ceremony | Fly.io, Railway, AWS ECS | Free-tier cold starts; vendor lock-in is acceptable here |
| Slot duration fixed at 30 minutes in DB check constraint | The brief is explicit; configurability would lie if the check still said 30 | Configurable duration | Changing to 15 minutes needs a migration |

---

## 5. API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/appointments` | Book a slot |
| `GET` | `/doctors/{id}/availability?date=YYYY-MM-DD` | Slots for that local date |
| `PATCH` | `/appointments/{id}/cancel` | Cancel with reason |
| `PATCH` | `/appointments/{id}/reschedule` | Move to a new slot |
| `GET` | `/patients/{id}/appointments` | Upcoming booked appointments, soonest first |
| `GET` | `/doctors` | Supporting: list seeded doctors |
| `GET` | `/patients` | Supporting: list seeded patients |
| `GET` | `/health` | Process + database ping |

Stable error envelope:

```json
{
  "error": {
    "code": "APPOINTMENT_SLOT_UNAVAILABLE",
    "message": "The selected appointment slot is no longer available.",
    "details": {}
  }
}
```

| HTTP | When |
| --- | --- |
| 201 | Booking created |
| 200 | Cancel, reschedule, reads |
| 404 | Unknown doctor, patient, or appointment |
| 409 | Slot taken, already cancelled, reschedule of cancelled |
| 422 | Validation and domain rule failures (past, hours, alignment, lead time) |
| 500 | Unexpected server errors only |

Seeded IDs (after `python -m app.seed`):

| Doctor | UUID |
| --- | --- |
| Dr. Amina Odhiambo (GP) | `550e8400-e29b-41d4-a716-446655440001` |
| Dr. James Mwangi (Pediatrics) | `550e8400-e29b-41d4-a716-446655440002` |
| Dr. Wanjiku Njoroge (Dermatology, no Tuesday) | `550e8400-e29b-41d4-a716-446655440003` |
| Dr. Samuel Otieno (Internal Medicine) | `550e8400-e29b-41d4-a716-446655440004` |
| Dr. Faith Wambui (Obstetrics) | `550e8400-e29b-41d4-a716-446655440005` |

Example booking (use a **future** Monday 10:00 Nairobi):

```http
POST /appointments
Content-Type: application/json

{
  "doctor_id": "550e8400-e29b-41d4-a716-446655440001",
  "patient_id": "660e8400-e29b-41d4-a716-446655440001",
  "start_at": "2026-08-24T09:00:00+03:00"
}
```

---

## 6. Running locally

**Requirements:** Docker (recommended) or Python 3.12 + PostgreSQL 16.

### Docker Compose (application + database)

```bash
git clone <your-fork-url>
cd clinic
cp .env.example .env
docker compose up --build
```

The API listens on `http://localhost:8000`. Migrations and sample data run on container start.

### Local Python against Compose Postgres

```bash
docker compose up -d db
cp .env.example .env
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Then open `http://localhost:8000/docs`.

### Tests

```bash
docker compose up -d db
docker compose --profile test run --rm testd
```

This runs lint and pytest inside Python 3.12 without installing Python on the host. Compose publishes Postgres on **host port 5433** so it does not collide with a local Postgres on 5432. The test runner talks to Postgres on the Docker network (`db:5432`). Override with `TEST_DATABASE_URL` if needed.

If `clinic_test` is missing (volume created before that script existed):

```sql
CREATE DATABASE clinic_test;
```

---

## 7. Environment variables

| Variable | Purpose | Example |
| --- | --- | --- |
| `DATABASE_URL` | Postgres URL. `postgres://` and `postgresql://` are rewritten to `postgresql+asyncpg://` | `postgresql+asyncpg://clinic:clinic@localhost:5433/clinic` |
| `DATABASE_SSL` | Enable TLS for hosted Postgres (Render) | `false` locally, `true` on Render |
| `CLINIC_TIMEZONE` | IANA zone for working hours and calendar dates | `Africa/Nairobi` |
| `MIN_BOOKING_NOTICE_MINUTES` | Lead time before a slot may be booked | `60` |
| `MAX_BOOKING_AHEAD_DAYS` | How far ahead a booking may be | `90` |
| `SEED_SAMPLE_DATA` | Seed 5 doctors / 5 patients on boot | `true` |
| `CORS_ORIGINS` | `*` or comma-separated origins | `*` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `PORT` | Listen port (Render sets this) | `8000` |

Do not commit `.env`. Use `.env.example` as the template.

---

## 8. Testing

### Automated (do this first)

From the project root, with Docker Desktop running:

```powershell
docker compose up -d db
docker compose --profile test run --rm testd
```

That installs dependencies in a Python 3.12 container, runs `ruff check .`, then `pytest -q` against `clinic_test`.

You should see a passing suite. If Postgres errors mention `clinic_test`, create it once (Compose publishes Postgres on **host port 5433**):

```sql
CREATE DATABASE clinic_test;
```

If you have Python 3.12 on the host instead:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://clinic:clinic@127.0.0.1:5433/clinic_test"
ruff check .
pytest -q
```

| Brief requirement | Test |
| --- | --- |
| Successful booking | `test_successful_booking` |
| Outside hours / past / taken / unaligned | `test_booking_*` |
| Availability for a date | `test_availability_calculation` |
| Cancel + slot free again | `test_cancel_appointment`, `test_slot_is_bookable_again_after_cancel` |
| Cancel already cancelled | `test_cancel_already_cancelled` |
| Reschedule + original slot free | `test_reschedule_appointment`, `test_original_slot_is_bookable_after_reschedule` |
| Reschedule cancelled / occupied / outside hours | `test_reschedule_*` |
| Patient upcoming list + 1-hour notice | `test_patient_upcoming_*`, `test_booking_too_soon` |
| Concurrent double-book | `test_concurrent_double_booking` |

### Manual (after the API is up)

```powershell
docker compose up --build
```

Open **http://localhost:8000/docs** (easiest) or **http://localhost:8000/redoc**.

| Role | UUID |
| --- | --- |
| Dr. Amina Odhiambo | `550e8400-e29b-41d4-a716-446655440001` |
| Grace Njeri (patient) | `660e8400-e29b-41d4-a716-446655440001` |
| Peter Kamau (patient) | `660e8400-e29b-41d4-a716-446655440002` |

Use a **future Monday** at `10:00+03:00`. Do not use a time within 60 minutes of now.

1. `GET /health` → `status: ok`
2. `GET /doctors` → five doctors
3. `GET /doctors/{amina}/availability?date=YYYY-MM-DD` — free slots have `status = available`
4. `POST /appointments` with Amina + Grace + an available `start_at`
5. Same body with Peter → `409 APPOINTMENT_SLOT_UNAVAILABLE`
6. `PATCH /appointments/{id}/cancel` with `{"reason": "Testing"}` → slot is `available` again
7. `PATCH /appointments/{id}/reschedule` to another free slot → original slot frees
8. `GET /patients/{grace}/appointments` → upcoming booked rows, soonest first

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/doctors
curl.exe "http://localhost:8000/doctors/550e8400-e29b-41d4-a716-446655440001/availability?date=2026-08-24"
```

Replace `2026-08-24` with a future Monday if that date is already past.

---

## 9. Deployment

**Provider: Render** (Docker web service + managed PostgreSQL).

Why Render, not AWS/GCP/Azure: this is a take-home. Render gives a public URL, Postgres, and a deploy hook without IAM theatre. Fly.io and Railway are equally valid; AWS ECS would demonstrate more cloud surface and more chances to fail the “it must be up” requirement.

**This workspace does not have a live URL.** Do not paste a URL you have not opened in a browser.

1. Push this repo to GitHub (`main` is the deploy branch).
2. In Render, apply the Blueprint from `render.yaml`, or create a PostgreSQL instance plus a Docker web service pointing at the repo.
3. Set `DATABASE_URL` from Render’s connection string (the app rewrites `postgres://` and strips libpq `sslmode`).
4. Set `DATABASE_SSL=true` if the URL does not already include `sslmode=require`.
5. Confirm `GET https://<your-service>.onrender.com/health` returns `{"status":"ok",...}`.
6. In Render, create a **Deploy Hook**. In GitHub → Settings → Secrets, add `RENDER_DEPLOY_HOOK`.
7. Put the public base URL at the top of this README.

`GET /health` is the Render health check path. It returns **503** if PostgreSQL is unreachable.

**Render free-tier notes:** free web services spin down after idle; the first request can take about a minute. Free Postgres expires after 30 days (14-day grace to upgrade). That is enough for this assessment if you submit before expiry.

---

## 10. CI/CD

```text
Pull request opened/updated
    → GitHub Actions workflow `CI`
    → install deps, ruff, pytest against a Postgres service

Merge / push to `main`
    → workflow `CI` (same checks)
    → workflow `Deploy`
        → run the same lint + tests
        → POST the Render deploy hook
        → Render builds the Dockerfile, runs `python -m app.entrypoint`
          (alembic upgrade, seed, uvicorn)
```

Secrets used: `RENDER_DEPLOY_HOOK` only. Nothing sensitive is in YAML.

---

## 11. Assumptions

- **Authentication is out of scope.** Clients send `doctor_id` / `patient_id`. This is a booking-engine assessment, not an identity assessment.
- **Clinic timezone is `Africa/Nairobi`.** Hours in `doctor_schedules` are naive local times in that zone. Instants are stored in UTC.
- **No overnight shifts, holidays, or per-day exceptions.** A day off = no schedule rows for that weekday.
- **Lunch** is two windows, not a special entity.
- **Reschedule does not change doctor.**
- **Patients may hold more than one future appointment** unless those appointments collide on a doctor slot.
- **Cancelled appointments are omitted** from `GET /patients/{id}/appointments` because “upcoming” means still happening.
- **Past appointments cannot be cancelled or rescheduled.**
- **Seed data is part of the demo**, not a production migration. Disable with `SEED_SAMPLE_DATA=false`.
- **Slot length is 30 minutes**, enforced by a check constraint, not a runtime config flag.

---

## 12. Limitations / future work

- No authentication, authorization, or audit trail of who cancelled.
- No rate limiting (would belong at the reverse proxy or a small SlowAPI layer).
- No holiday calendar or doctor-specific timezone column (the doctor table can grow a `timezone` later; availability already takes a zone name).
- Reschedule does not keep previous start times.
- No notifications (SMS/email).
- Availability is computed on read; a slot table would only pay off at much larger scale.
- Render free web services sleep; the first request after idle can be slow.
- Unique `(doctor_id, start_at)` is equivalent to “no overlap” only while every appointment is a 30-minute aligned slot. If duration becomes variable, replace it with a `btree_gist` exclusion on `tstzrange(start_at, end_at)`.

### What an interviewer can reasonably challenge

These are intentional, not accidents:

- **No auth.** The brief asked for a booking engine. Fake JWT would hide that work.
- **In-place reschedule.** Atomic and simple; it does not keep a revision history.
- **No Redis.** The race is a uniqueness problem, not a cache problem.
- **Weekday windows, not a holiday calendar.** Enough for five doctors; not a hospital roster.

---

## Time and date strategy

| Layer | Rule |
| --- | --- |
| Database | `timestamptz` only for instants. Session/zone inside Postgres is irrelevant; values are UTC. |
| Application | `datetime.now(UTC)` for “now”. Convert to `ZoneInfo(CLINIC_TIMEZONE)` for weekday and clock time. |
| Working hours | `TIME` without zone = Nairobi wall clock. |
| API | `pydantic.AwareDatetime` — naive values are `422`. |
| Alignment | Minutes `00` or `30` in **clinic local time**, so a future `UTC+5:30` clinic still works. Nairobi happens to share UTC’s minute-of-hour; the code does not rely on that. |

---

## Security (deliberate, scoped)

Addressed: parameterized SQLAlchemy (no string SQL for user input), Pydantic validation, secrets via env, CORS from config, error codes that do not dump internals, dependency install in CI.

Explicitly **not** built: login, RBAC, rate limits, WAF. UUIDs are unguessable enough for a demo and not a substitute for auth.

---

## Section 4 — AI reflection

See [AI_REFLECTION.md](AI_REFLECTION.md).
