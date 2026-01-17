#app/config.py
from __future__ import annotations

from pydantic import BaseModel
import os


class Settings(BaseModel):
    # === Platform bot (той, де оренда/маркетплейс) ===
    PLATFORM_BOT_TOKEN: str = os.getenv("PLATFORM_BOT_TOKEN", "")

    # === Webhook / server ===
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "")  # напр: https://your-app.up.railway.app
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/tg/webhook")  # один endpoint на всі боти
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")  # опціонально: секрет для перевірки запитів

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))

    # === DB (пізніше підключимо) ===
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # === Runtime ===
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"


settings = Settings()