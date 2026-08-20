import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _asyncpg_ssl(verify: bool):
    """Render Postgres presents a self-signed cert. Encrypt, don't verify, by default."""
    if verify:
        return True
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def create_engine_from_url(
    database_url: str,
    ssl: bool = False,
    *,
    null_pool: bool = False,
    ssl_verify: bool = False,
):
    connect_args = {"ssl": _asyncpg_ssl(ssl_verify)} if ssl else {}
    kwargs: dict = {"pool_pre_ping": True, "connect_args": connect_args}
    if null_pool:
        kwargs["poolclass"] = NullPool
    return create_async_engine(database_url, **kwargs)


settings = get_settings()
engine = create_engine_from_url(
    settings.async_database_url,
    ssl=settings.use_database_ssl,
    ssl_verify=settings.verify_database_ssl,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
