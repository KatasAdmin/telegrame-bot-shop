import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    ENV: str = os.getenv("ENV", "prod")
    PLATFORM_BOT_TOKEN: str = os.getenv("PLATFORM_BOT_TOKEN", "")  # потім підключимо aiogram
    BASE_URL: str = os.getenv("BASE_URL", "")  # домен Railway, потім для webhook

settings = Settings()