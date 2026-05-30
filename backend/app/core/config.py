from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./doodlestory.db"
    session_secret: str = Field(min_length=16)
    admin_emails: str = ""
    doodlestory_storage_root: str = "./storage"
    frontend_origin: str = "http://127.0.0.1:3000"
    log_level: str = "INFO"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model: str = ""
    xg_api_key: str = ""
    xg_api_base_url: str = "https://api.xgapi.top"

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def storage_root(self) -> Path:
        configured = Path(self.doodlestory_storage_root)
        if configured.is_absolute():
            return configured
        return (PROJECT_ROOT / configured).resolve()

    @property
    def resolved_database_url(self) -> str:
        if not self.database_url.startswith("sqlite:///"):
            return self.database_url

        raw_path = self.database_url.removeprefix("sqlite:///")
        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path

        return f"sqlite:///{quote(str(db_path.resolve()))}"

    @property
    def frontend_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.frontend_origin.split(",")
            if origin.strip()
        ]

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
