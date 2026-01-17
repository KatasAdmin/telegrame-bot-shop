# rent_platform/config.py
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    WEBHOOK_URL: str  # https://your-app.up.railway.app
    WEBHOOK_PATH: str = "/tg/webhook"

    # Railway/Render/Heroku
    PORT: int = 8080

    # dev flag
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()