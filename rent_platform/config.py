# rent_platform/config.py

import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    # PLATFORM
    PLATFORM_BOT_TOKEN: str | None = os.getenv("PLATFORM_BOT_TOKEN")

    # TELEGRAM
    TELEGRAM_API_URL: str = "https://api.telegram.org"

    # ENV
    ENV: str = os.getenv("ENV", "dev")

    class Config:
        env_file = ".env"


settings = Settings()