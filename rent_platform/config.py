from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    WEBHOOK_URL: str
    WEBHOOK_PATH: str = "/tg/webhook"

    TENANT_WEBHOOK_PREFIX: str = "/tg/t"

    DATABASE_URL: str

    # ✅ Admins (comma-separated ids)
    ADMIN_USER_IDS: str = ""  # приклад: "123,456"

    PORT: int = 8080
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()