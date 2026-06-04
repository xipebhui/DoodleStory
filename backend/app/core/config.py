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
    storage_backend: str = "local"
    doodlestory_storage_root: str = "./storage"
    qiniu_access_key: str = ""
    qiniu_secret_key: str = ""
    qiniu_bucket: str = ""
    qiniu_bucket_domain: str = ""
    qiniu_thumbnail_fop: str = "imageView2/1/w/320/h/568/format/webp/q/75"
    qny_access_key: str = ""
    qny_secret_key: str = ""
    qny_bucket: str = ""
    qny_domain: str = ""
    local_thumbnail_width: int = 320
    local_thumbnail_height: int = 568
    frontend_origin: str = "http://127.0.0.1:3000"
    log_level: str = "INFO"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model: str = ""
    siliconflow_temperature: float = 0.8
    prompt_trace_log_max_chars: int = 60000
    xg_api_key: str = ""
    xg_api_base_url: str = "https://api.xgapi.top"
    apexerapi_api_key: str = ""
    apexerapi_base: str = ""
    apexerapi_proxy_url: str = ""
    xg_proxy_url: str = ""
    xg_request_max_attempts: int = 3
    xg_request_retry_backoff_seconds: float = 2.0
    image_provider_debug_log_raw_io: bool = False
    image_provider_debug_log_raw_max_chars: int = 20000
    douyin_downloader_root: str = ""
    douyin_downloader_python: str = ""
    douyin_cookie: str = ""
    douyin_cookie_file: str = ""
    douyin_download_timeout_seconds: int = 180

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
