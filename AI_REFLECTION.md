# Section 4 — AI reflection

Bullet answers to the assessment questions.

## 1. What did you use AI for across the four sections?

- **Section 1:** Decision table (partial unique index vs row locks vs Redis), timezone strategy, and what not to build.
- **Section 2:** FastAPI / SQLAlchemy 2 layout, Alembic revision, domain helpers, pytest fixtures, error envelope.
- **Section 3:** GitHub Actions Postgres service, Render `render.yaml`, Docker entrypoint (migrate → seed → serve).
- **Section 4:** Structuring this file from the four questions. The answers are from the actual work.

AI was not an unreviewed code generator. Booking rules were checked against the brief (hours, cancel reason, reschedule of cancelled, database uniqueness).

## 2. Give one example where an AI suggestion improved the work. What did you prompt it with?

**Improvement:** partial unique index `UNIQUE (doctor_id, start_at) WHERE status = 'booked'`.

A unique constraint on `(doctor_id, start_at)` without the `WHERE` would keep cancelled rows on the key, so the slot could never be booked again. The partial index keeps history and still serializes concurrent bookings. That also justified in-place reschedule (one row, one uniqueness check).

**Prompt (paraphrased from the brief):**  
*The database must enforce appointment uniqueness rather than relying solely on application-level checks. Two patients must not book the same slot at the same time. Cancelled appointments must become bookable again and history must be preserved.*

## 3. Give one example where AI output was wrong or incomplete and how you caught it.

**Wrong suggestion:** align 30-minute slots on the stored UTC timestamp.

Nairobi is `UTC+3` with no DST, so minutes happen to match UTC *today*. A `UTC+5:30` clinic would pass UTC alignment and still be a bad wall-clock slot.

**How it was caught:** converting `2026-08-24T09:00:00+03:00` → `06:00Z` and asking what happens in `Asia/Kolkata`, instead of assuming “just use UTC.”

**Change:** `is_slot_aligned` uses clinic local time; covered by `test_alignment_uses_clinic_local_time_not_utc`.

A second miss: hosted `DATABASE_URL` is often `postgres://` with libpq `sslmode`. That would break on Render. Config now rewrites the driver and strips `sslmode`.

## 4. Name two decisions you made without AI. Why did you trust your own judgment there?

**1. Authentication is out of scope.**  
The brief never asked for users, roles, or tokens. A decorative JWT would steal time from uniqueness and timezone design, which are scored.

**2. No Redis, no slot table, no event sourcing.**  
Five doctors and a 30-minute grid do not need a cache. The failure that matters is a lost update on double book — a data-integrity problem PostgreSQL already solves.

## Verification note

Local tests: 36 passed. Live health check succeeded at https://clinic-booking-api-8b9f.onrender.com/health.
