from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.seed import DOCTORS, PATIENTS

NAIROBI = ZoneInfo("Africa/Nairobi")

GP_ID = str(DOCTORS[0]["id"])
DERM_ID = str(DOCTORS[2]["id"])
PATIENT_A = str(PATIENTS[0]["id"])
PATIENT_B = str(PATIENTS[1]["id"])
PATIENT_C = str(PATIENTS[2]["id"])


def next_weekday(weekday: int, min_days: int = 3):
    today = datetime.now(NAIROBI).date()
    days = (weekday - today.weekday()) % 7
    if days < min_days:
        days += 7
    return today + timedelta(days=days)


def nairobi(day, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=NAIROBI)


def iso(day, hour: int, minute: int = 0) -> str:
    return nairobi(day, hour, minute).isoformat()
