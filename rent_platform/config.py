class Settings(BaseSettings):
    BOT_TOKEN: str
    WEBHOOK_URL: str
    WEBHOOK_PATH: str = "/tg/webhook"

    TENANT_WEBHOOK_PREFIX: str = "/tg/t"

    DATABASE_URL: str

    ADMIN_USER_IDS: str = ""  # "123,456,789"

    PORT: int = 8080
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def admin_ids(self) -> set[int]:
        if not self.ADMIN_USER_IDS:
            return set()
        return {int(x.strip()) for x in self.ADMIN_USER_IDS.split(",") if x.strip()}