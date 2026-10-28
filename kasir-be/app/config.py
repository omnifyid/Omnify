from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/kasir"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 30
    # Stored as comma-separated string to avoid pydantic-settings JSON-decode
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    media_dir: str = "media"
    frontend_url: str = "http://localhost:5173"
    resend_api_key: str | None = None
    resend_from_email: str = "Kasir <no-reply@example.com>"
    redis_url: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
