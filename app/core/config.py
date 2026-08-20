from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict


def _asyncpg_url(raw: str) -> str:
    url = raw
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.pop("sslmode", None)
    query.pop("ssl", None)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _url_requires_ssl(raw: str) -> bool:
    parsed = urlparse(raw)
    query = dict(parse_qsl(parsed.query))
    return query.get("sslmode", "").lower() in {"require", "verify-ca", "verify-full"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://clinic:clinic@localhost:5433/clinic"
    database_ssl: bool = False
    database_ssl_verify: bool = False

    clinic_timezone: str = "Africa/Nairobi"
    min_booking_notice_minutes: int = 60
    max_booking_ahead_days: int = 90
    seed_sample_data: bool = True

    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def async_database_url(self) -> str:
        """Accept postgres:// / postgresql:// from hosts like Render; drop libpq sslmode."""
        return _asyncpg_url(self.database_url)

    @property
    def use_database_ssl(self) -> bool:
        return self.database_ssl or _url_requires_ssl(self.database_url)

    @property
    def verify_database_ssl(self) -> bool:
        parsed = urlparse(self.database_url)
        mode = dict(parse_qsl(parsed.query)).get("sslmode", "").lower()
        if mode in {"verify-ca", "verify-full"}:
            return True
        return self.database_ssl_verify

    @property
    def sync_database_url(self) -> str:
        return self.async_database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
