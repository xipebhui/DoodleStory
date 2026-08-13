from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LIO_MODEL = "gemini-3.1-flash-lite-preview-thinking-minimal"


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./doodlestory.db"
    session_secret: str = Field(min_length=16)
    admin_emails: str = ""
    doodlestory_frontend_dist: str = ""
    storage_backend: str = "local"
    doodlestory_storage_root: str = "./storage"
    object_storage_keep_local_mirror: bool = False
    qiniu_access_key: str = ""
    qiniu_secret_key: str = ""
    qiniu_bucket: str = ""
    qiniu_bucket_domain: str = ""
    qiniu_thumbnail_fop: str = "imageView2/1/w/320/h/568/format/webp/q/75"
    qny_access_key: str = ""
    qny_secret_key: str = ""
    qny_bucket: str = ""
    qny_public_base_url: str = ""
    qny_use_https: bool = True
    qny_domain: str = ""
    aliyun_oss_access_key_id: str = ""
    aliyun_oss_access_key_secret: str = ""
    aliyun_oss_bucket: str = ""
    aliyun_oss_endpoint: str = ""
    aliyun_oss_public_base_url: str = ""
    local_thumbnail_width: int = 320
    local_thumbnail_height: int = 568
    frontend_origin: str = "http://127.0.0.1:3000"
    log_level: str = "INFO"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model: str = ""
    siliconflow_temperature: float = 0.8
    lio_api_key: str = ""
    lio_base_url: str = ""
    lio_model: str = DEFAULT_LIO_MODEL
    lio_temperature: float = 0.8
    text_fallback_api_key: str = ""
    text_fallback_base_url: str = ""
    text_fallback_model: str = ""
    text_fallback_max_attempts: int = Field(default=3, ge=1)
    text_fallback_retry_backoff_seconds: float = Field(default=2.0, ge=0)
    agent_model: str = "gpt-5.5"
    agent_request_timeout_seconds: int = Field(default=120, ge=1)
    agent_primary_retry_attempts: int = Field(default=1, ge=0, le=1)
    agent_retry_backoff_seconds: float = Field(default=0.5, ge=0)
    agent_worker_concurrency: int = Field(default=1, ge=1)
    agent_context_message_limit: int = Field(default=200, ge=1, le=1000)
    native_agent_default_route: str = "huomiao_responses"
    native_agent_huomiao_model: str = "gpt-5.5"
    native_agent_siliconflow_model: str = "deepseek-ai/DeepSeek-V3.2"
    mlflow_tracing_enabled: bool = False
    mlflow_tracking_uri: str = ""
    mlflow_experiment_name: str = "doodlestory-agent-local"
    mlflow_trace_content: bool = False
    character_extraction_temperature: float = 0.1
    prompt_trace_log_max_chars: int = 60000
    image_provider: str = "qy"
    image_gateway_api_key: str = ""
    image_gateway_base_url: str = "http://192.129.209.36:3001/v1"
    xg_api_key: str = ""
    xg_base_url: str = "https://api.xgapi.top"
    xg_image_quality: str = "1k"
    grokcli_executable: str = "grokcli"
    grokcli_home: str = ""
    grokcli_image_model: str = "grok-imagine-image-quality"
    grokcli_image_edit_model: str = "grok-imagine-image"
    grokcli_image_resolution: str = "2k"
    grokcli_timeout_seconds: int = Field(default=300, ge=30)
    grokcli_request_max_attempts: int = Field(default=2, ge=1, le=5)
    grokcli_retry_backoff_seconds: float = Field(default=2.0, ge=0)
    grokcli_video_model: str = "grok-imagine-video-1.5"
    grokcli_video_resolution: str = "720p"
    grokcli_video_timeout_seconds: int = Field(default=660, ge=60)
    apexerapi_api_key: str = ""
    apexerapi_base: str = ""
    apexerapi_proxy_url: str = ""
    xg_request_max_attempts: int = 3
    xg_request_retry_backoff_seconds: float = 2.0
    image_provider_timeout_retry_attempts: int = Field(default=3, ge=0)
    task_worker_concurrency: int = Field(default=3, ge=1)
    image_generation_concurrency: int = Field(default=3, ge=1)
    image_job_concurrency: int = Field(default=6, ge=1)
    image_job_user_concurrency: int = Field(default=2, ge=1)
    image_job_lease_seconds: int = Field(default=1800, ge=60)
    video_task_worker_concurrency: int = Field(default=1, ge=1)
    task_failure_alert_webhook_url: str = ""
    task_failure_alert_timeout_seconds: int = Field(default=10, ge=1)
    task_failure_alert_task_base_url: str = ""
    image_provider_debug_log_raw_io: bool = False
    image_provider_debug_log_raw_max_chars: int = 20000
    douyin_import_service_base_url: str = "http://127.0.0.1:8010"
    siliconflow_vision_model: str = "Qwen/Qwen3-VL-32B-Instruct"
    siliconflow_audio_model: str = ""
    video_tts_provider: str = "siliconflow"
    video_tts_model: str = "FunAudioLLM/CosyVoice2-0.5B"
    video_tts_response_format: str = "mp3"
    video_tts_sample_rate: int = Field(default=32000, ge=8000)
    video_tts_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    video_tts_gain: float = 0.0
    video_tts_timeout_seconds: int = Field(default=1200, ge=30)
    doubao_voice_gen_appid: str = ""
    doubao_voice_gen_ak: str = ""
    doubao_voice_gen_sk: str = ""
    doubao_voice_gen_base_url: str = (
        "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    )
    doubao_voice_gen_resource_id: str = "seed-tts-2.0"
    doubao_voice_gen_model: str = "seed-tts-2.0-standard"
    doubao_voice_gen_speaker: str = "zh_female_xinlingjitang_uranus_bigtts"
    doubao_voice_gen_format: str = "mp3"
    doubao_voice_gen_sample_rate: int = Field(default=24000, ge=8000)
    doubao_voice_gen_speech_rate: int = Field(default=0, ge=-50, le=100)
    doubao_voice_gen_loudness_rate: int = Field(default=0, ge=-50, le=100)
    doubao_voice_gen_timeout_seconds: int = Field(default=120, ge=10)
    ffprobe_executable: str = "ffprobe"
    remotion_project_dir: Path = (
        Path(__file__).resolve().parents[3] / "remotion"
    )
    remotion_node_executable: str = "node"
    remotion_render_timeout_seconds: int = Field(default=1200, ge=30)
    local_whisper_model: str = "tiny"
    local_whisper_device: str = "auto"
    local_whisper_compute_type: str = "default"
    comic_video_service_base_url: str = "http://127.0.0.1:51103"
    comic_video_service_api_key: str = ""
    comic_video_poll_interval_seconds: float = Field(default=5.0, ge=0.2)
    comic_video_poll_timeout_seconds: int = Field(default=3600, ge=60)
    comic_video_episode_theme: str = "daily"
    comic_video_episode_width: int = Field(default=1080, ge=64)
    comic_video_episode_height: int = Field(default=1920, ge=64)
    comic_video_episode_fps: int = Field(default=10, ge=1, le=120)
    comic_video_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    ytb_publish_url: str = ""
    ytb_publish_api_key: str = ""
    ytb_publish_timeout_seconds: int = Field(default=60, ge=5, le=300)

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
    def frontend_dist_path(self) -> Path | None:
        if not self.doodlestory_frontend_dist.strip():
            return None
        configured = Path(self.doodlestory_frontend_dist)
        if configured.is_absolute():
            return configured.resolve()
        return (PROJECT_ROOT / configured).resolve()

    @property
    def resolved_database_url(self) -> str:
        if not self.database_url.startswith("sqlite:///"):
            return self.database_url

        raw_path = self.database_url.removeprefix("sqlite:///")
        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path

        return f"sqlite:///{db_path.resolve().as_posix()}"

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

    @property
    def lio_openai_base_url(self) -> str:
        base_url = self.lio_base_url.strip().rstrip("/")
        if base_url and not base_url.endswith("/v1"):
            return f"{base_url}/v1"
        return base_url

    @property
    def text_fallback_openai_base_url(self) -> str:
        base_url = self.text_fallback_base_url.strip().rstrip("/")
        if base_url and not base_url.endswith("/v1"):
            return f"{base_url}/v1"
        return base_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
