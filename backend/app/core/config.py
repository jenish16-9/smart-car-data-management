import secrets

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Car Data Management API"
    api_prefix: str = "/api/v1"
    environment: str = "development"
    frontend_origin: str = "http://localhost:5173"

    postgres_url: str = "postgresql+asyncpg://localhost:5432/smart_car"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "smart_car"

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    bcrypt_rounds: int = 12
    device_delayed_after_seconds: int = 90
    device_offline_after_seconds: int = 300
    audio_classifier_backend: str = "mock"
    audio_model_path: str = "ml_artifacts/audio-baseline.joblib"
    audio_upload_max_bytes: int = 10_000_000

    # Development login seed; only applied when environment == "development".
    dev_admin_email: str = ""
    dev_admin_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

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
