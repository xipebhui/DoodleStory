from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    AgentRunStatus,
    NativeAgentItemType,
    NativeAgentStepStatus,
    NativeAgentStepType,
)


class NativeAgentConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="新图片创作", min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("会话标题不能为空")
        return normalized


class NativeAgentYoutubePublishConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility: Literal["public", "private", "unlisted"] = "public"
    planned_publish_at: datetime | None = None
    notify_subscribers: bool = True
    confirmed: bool


class NativeAgentRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=20_000)
    skill_version_id: str = Field(min_length=1, max_length=32)
    style_id: str | None = Field(default=None, max_length=32)
    youtube_channel_id: str | None = Field(default=None, max_length=32)
    youtube_publishable_video_id: str | None = Field(default=None, max_length=32)
    youtube_publish_confirmation: NativeAgentYoutubePublishConfirmation | None = None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("消息内容不能为空")
        return value

    @model_validator(mode="after")
    def validate_youtube_context(self) -> "NativeAgentRunCreate":
        values = (
            self.youtube_channel_id,
            self.youtube_publishable_video_id,
            self.youtube_publish_confirmation,
        )
        if any(value is not None for value in values) and not all(
            value is not None for value in values
        ):
            raise ValueError("频道、可发布视频和发布确认必须同时提供")
        if (
            self.youtube_publish_confirmation is not None
            and not self.youtube_publish_confirmation.confirmed
        ):
            raise ValueError("真实发布前必须明确确认")
        return self


class NativeAgentItemRead(BaseModel):
    id: str
    sequence: int
    item_type: NativeAgentItemType
    payload: dict[str, object]
    created_at: datetime


class NativeAgentImageRead(BaseModel):
    id: str
    asset_id: str
    prompt: str
    image_model: str
    aspect_ratio: str
    width: int | None
    height: int | None
    created_at: datetime


class NativeAgentAudioRead(BaseModel):
    id: str
    asset_id: str
    text: str
    provider: str
    resource_id: str
    model: str
    speaker: str
    response_format: str
    sample_rate: int
    duration_ms: int | None
    speed: float
    speech_rate: int
    created_at: datetime


class NativeAgentSubtitleRead(BaseModel):
    id: str
    audio_id: str
    asset_id: str
    provider: str
    model: str
    language: str
    text: str
    cues: list[dict[str, object]]
    duration_ms: int
    created_at: datetime


class NativeAgentVideoRead(BaseModel):
    id: str
    asset_id: str
    bgm_asset_id: str | None
    template_id: str
    renderer_version: str
    scenes: list[dict[str, object]]
    duration_ms: int
    duration_in_frames: int
    fps: int
    width: int
    height: int
    created_at: datetime


class NativeAgentExternalContentRead(BaseModel):
    id: str
    content_asset_id: str
    platform: str
    content_type: str | None
    source_url: str
    resolved_url: str
    source_content_id: str | None
    title: str | None
    description: str | None
    author_name: str | None
    publish_time: str | None
    publish_timestamp: int | None
    tags: list[str]
    metrics: dict[str, object]
    excerpt: str
    created_at: datetime


class NativeAgentStepRead(BaseModel):
    id: str
    sequence: int
    step_type: NativeAgentStepType
    status: NativeAgentStepStatus
    name: str
    tool_call_id: str | None
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None


class NativeAgentEventRead(BaseModel):
    id: str
    sequence: int
    event_type: str
    payload: dict[str, object]
    created_at: datetime


class NativeAgentRunRead(BaseModel):
    id: str
    conversation_id: str
    skill_version_id: str
    skill_name: str
    skill_version: int
    style_id: str | None
    style_name: str | None
    youtube_channel_id: str | None
    youtube_channel_name: str | None
    youtube_publishable_video_id: str | None
    youtube_publishable_video_title: str | None
    youtube_publish_confirmation: dict[str, object] | None
    status: AgentRunStatus
    model: str
    model_call_count: int
    image_call_count: int
    speech_call_count: int
    subtitle_call_count: int
    video_call_count: int
    final_output: str | None
    error_code: str | None
    error_message: str | None
    items: list[NativeAgentItemRead] = Field(default_factory=list)
    images: list[NativeAgentImageRead] = Field(default_factory=list)
    audios: list[NativeAgentAudioRead] = Field(default_factory=list)
    subtitles: list[NativeAgentSubtitleRead] = Field(default_factory=list)
    videos: list[NativeAgentVideoRead] = Field(default_factory=list)
    external_contents: list[NativeAgentExternalContentRead] = Field(
        default_factory=list
    )
    steps: list[NativeAgentStepRead] = Field(default_factory=list)
    events: list[NativeAgentEventRead] = Field(default_factory=list)
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NativeAgentConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime


class NativeAgentConversationDetailRead(NativeAgentConversationRead):
    runs: list[NativeAgentRunRead] = Field(default_factory=list)


class NativeAgentCapabilityRead(BaseModel):
    loop: Literal["agents_sdk"]
    tools: list[
        Literal[
            "generate_image",
            "generate_speech",
            "generate_subtitles",
            "render_story_video",
            "publish_youtube_video",
            "capture_wechat_article",
        ]
    ]
    image_review: Literal["native_model_vision"]
