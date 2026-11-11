import secrets

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# libpq-only options that asyncpg rejects; hosted providers (Neon, Supabase) put them in their URLs.
_UNSUPPORTED_PG_PARAMS = {"channel_binding", "options"}


def normalize_postgres_url(url: str) -> str:
    """Make a hosted-provider URL usable with SQLAlchemy + asyncpg.

    - ``postgres://`` / ``postgresql://`` become ``postgresql+asyncpg://``.
    - ``sslmode=`` (libpq) becomes ``ssl=`` (asyncpg); unsupported libpq options are dropped.
    - Percent-encoded user names / passwords are decoded by SQLAlchemy and re-encoded safely.
    """
    parsed = make_url(url)
    if parsed.drivername in ("postgres", "postgresql"):
        parsed = parsed.set(drivername="postgresql+asyncpg")
    if not parsed.drivername.startswith("postgresql+asyncpg"):
        return url
    query = {k: v for k, v in parsed.query.items() if k not in _UNSUPPORTED_PG_PARAMS}
    if "sslmode" in query:
        query.setdefault("ssl", query.pop("sslmode"))
    return parsed.set(query=query).render_as_string(hide_password=False)


def redact_url(url: str) -> str:
    """URL with the password hidden, safe for logs and messages."""
    try:
        return make_url(url).render_as_string(hide_password=True) if "://" in url else "<invalid url>"
    except Exception:  # noqa: BLE001 - never leak the raw value in an error
        return "<invalid url>"


class Settings(BaseSettings):
    app_name: str = "Smart Car Data Management API"
    api_prefix: str = "/api/v1"
    environment: str = "development"
    frontend_origin: str = "http://localhost:5173"

    postgres_url: str = "postgresql+asyncpg://localhost:5432/smart_car"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "smart_car"
    mongodb_timeout_ms: int = 5000

    # A device whose last heartbeat is older than this becomes DELAYED (ACTIVE/WARNING only).
    device_heartbeat_timeout_seconds: int = 300
    low_battery_warning_percent: int = 15

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    bcrypt_rounds: int = 12

    # Development login seed; only applied when environment == "development".
    dev_admin_email: str = ""
    dev_admin_password: str = ""
    # Password for the demo driver created by `python -m app.db.seed_demo`. Never printed.
    # If empty, the seed does not create the driver account.
    demo_driver_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @field_validator("postgres_url")
    @classmethod
    def _normalize_postgres_url(cls, value: str) -> str:
        return normalize_postgres_url(value)

    @model_validator(mode="after")
    def _require_jwt_secret(self) -> "Settings":
        if self.jwt_secret:
            return self
        if self.environment != "development":
            raise ValueError("JWT_SECRET must be set when ENVIRONMENT is not 'development'")
        # Random per-process secret: tokens stop working after a restart.
        self.jwt_secret = secrets.token_urlsafe(48)
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


settings = Settings()
