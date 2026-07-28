from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class YoutubeChannelProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str | None = Field(default=None, max_length=120)
    account_positioning: str | None = Field(default=None, max_length=4000)
    target_audience: str | None = Field(default=None, max_length=4000)
    stage_goal: str | None = Field(default=None, max_length=4000)
    ai_definition: str | None = Field(default=None, max_length=12000)
    operation_notes: str | None = Field(default=None, max_length=12000)

    @field_validator("*")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class YoutubeBenchmarkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(default="youtube", min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    platform_account_id: str | None = Field(default=None, max_length=160)
    profile_url: HttpUrl
    notes: str | None = Field(default=None, max_length=4000)


class YoutubeBenchmarkRead(BaseModel):
    id: str
    platform: str
    name: str
    platform_account_id: str | None
    profile_url: str
    notes: str | None
    created_at: datetime


class YoutubeUploadedVideoRead(BaseModel):
    id: str
    youtube_video_id: str
    publish_task_id: str | None
    source_native_agent_video_id: str | None
    title: str | None
    visibility: str | None
    views: int | None
    likes: int | None
    uploaded_at: datetime
    remote_last_sync_at: datetime | None
    last_sync_error: str | None


class YoutubeChannelSummaryRead(BaseModel):
    id: str
    channel_id: str
    title: str
    handle: str | None
    avatar_url: str | None
    remote_status: str
    alias: str | None
    account_positioning: str | None
    total_subscribers: int | None
    total_views: int | None
    total_watch_time_hours: float | None
    total_videos: int | None
    last_sync_success_at: datetime | None
    last_sync_error: str | None


class YoutubePublishTaskRead(BaseModel):
    id: str
    channel_id: str
    publishable_video_id: str
    source_native_agent_video_id: str
    remote_task_id: str | None
    status: str
    remote_status: str | None
    title: str
    thumbnail_url: str | None
    video_url: str
    visibility: str
    planned_publish_at: datetime
    confirmed_at: datetime
    last_status_checked_at: datetime | None
    completed_at: datetime | None
    youtube_video_id: str | None
    youtube_url: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime


class YoutubePublishTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publishable_video_id: str = Field(min_length=1, max_length=32)
    visibility: Literal["public", "private", "unlisted"] = "public"
    planned_publish_at: datetime | None = None
    notify_subscribers: bool = True
    confirmed: bool
    idempotency_key: str = Field(min_length=8, max_length=160)


class YoutubeChannelDetailRead(YoutubeChannelSummaryRead):
    account_email: str | None
    target_audience: str | None
    stage_goal: str | None
    ai_definition: str | None
    operation_notes: str | None
    analytics: dict[str, object] | None
    benchmarks: list[YoutubeBenchmarkRead]
    publish_tasks: list[YoutubePublishTaskRead]


class PublishableVideoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_native_agent_video_id: str = Field(min_length=1, max_length=32)
    thumbnail_url: HttpUrl | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    planned_publish_at: datetime | None = None
    contains_synthetic_media: bool = True
    review_status: Literal["draft", "approved"] = "draft"


class PublishableVideoRead(BaseModel):
    id: str
    source_native_agent_video_id: str
    video_url: str
    thumbnail_url: str | None
    title: str
    description: str
    tags: list[str]
    planned_publish_at: datetime | None
    contains_synthetic_media: bool
    review_status: str
    created_at: datetime
