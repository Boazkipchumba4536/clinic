from __future__ import annotations

import os

# Force a dedicated test database before any application import.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://clinic:clinic@127.0.0.1:5433/clinic_test",
)
os.environ.setdefault("CLINIC_TIMEZONE", "Africa/Nairobi")
os.environ.setdefault("MIN_BOOKING_NOTICE_MINUTES", "60")
os.environ.setdefault("MAX_BOOKING_AHEAD_DAYS", "90")
os.environ.setdefault("DATABASE_SSL", "false")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import database as db
from app.core.config import get_settings
from app.core.database import Base
from app.main import app
from app.seed import seed

get_settings.cache_clear()
settings = get_settings()
db.engine = db.create_engine_from_url(
    settings.async_database_url, ssl=False, null_pool=True
)
db.SessionLocal = async_sessionmaker(db.engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def client() -> AsyncClient:
    await db.engine.dispose()
    try:
        async with db.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        if os.getenv("TEST_DATABASE_URL"):
            raise
        pytest.skip(
            "PostgreSQL is not reachable at TEST_DATABASE_URL. "
            "Start it with: docker compose up -d db"
        )

    async with db.engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)

    async with db.SessionLocal() as session:
        await seed(session)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    await db.engine.dispose()
