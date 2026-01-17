from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram (platform bot)
    BOT_TOKEN: str
    WEBHOOK_URL: str
    WEBHOOK_PATH: str = "/tg/webhook"

    # Tenant webhooks (for rented bots)
    TENANT_WEBHOOK_PREFIX: str = "/tg/t"

    # DB
    DATABASE_URL: str

    # Railway/Render/Heroku
    PORT: int = 8080

    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()