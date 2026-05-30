from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./doodlestory.db"
    session_secret: str = Field(min_length=16)
    admin_emails: str = ""
    doodlestory_storage_root: str = "./storage"
    frontend_origin: str = "http://127.0.0.1:3000"

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def storage_root(self) -> Path:
        return Path(self.doodlestory_storage_root).resolve()

    @property
    def admin_email_set(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.admin_emails.split(",")
            if email.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
