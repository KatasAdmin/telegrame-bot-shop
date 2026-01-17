# rent_platform/config.py

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # === BOT / PLATFORM ===
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")

    # === SERVER ===
    PORT: int = Field(8080, env="PORT")
    WEBHOOK_URL: str = Field(..., env="WEBHOOK_URL")

    # === ENV ===
    ENV: str = Field("prod", env="ENV")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()