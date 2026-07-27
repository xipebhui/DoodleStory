from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class NativeAgentRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=20_000)
    skill_version_id: str = Field(min_length=1, max_length=32)
    style_id: str | None = Field(default=None, max_length=32)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("消息内容不能为空")
        return value


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
    status: AgentRunStatus
    model: str
    model_call_count: int
    image_call_count: int
    speech_call_count: int
    final_output: str | None
    error_code: str | None
    error_message: str | None
    items: list[NativeAgentItemRead] = Field(default_factory=list)
    images: list[NativeAgentImageRead] = Field(default_factory=list)
    audios: list[NativeAgentAudioRead] = Field(default_factory=list)
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
    tools: list[Literal["generate_image", "generate_speech"]]
    image_review: Literal["native_model_vision"]
