from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Car Data Management API"
    api_prefix: str = "/api/v1"
    environment: str = "development"
    frontend_origin: str = "http://localhost:5173"
    jwt_secret: str = "replace-this-development-secret"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()

