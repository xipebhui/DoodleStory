from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    AgentConversationStatus,
    AgentMessageRole,
    AgentRunStatus,
    AgentStepStatus,
    AgentStepType,
)
from app.schemas.common import OrmModel, PageInfo, TimestampFields


class AgentResourceKind(StrEnum):
    style = "style"
    character = "character"
    task = "task"
    panel = "panel"
    image_version = "image_version"


class AgentResourceRef(BaseModel):
    kind: AgentResourceKind
    id: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=160)


class AgentConversationCreate(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("会话标题不能为空")
        return normalized


class AgentMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    resource_refs: list[AgentResourceRef] = Field(default_factory=list, max_length=50)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("消息内容不能为空")
        return value


class AgentConversationRead(TimestampFields):
    id: str
    title: str
    status: AgentConversationStatus
    last_message_at: datetime


class AgentMessageRead(OrmModel):
    id: str
    conversation_id: str
    turn_id: str | None
    role: AgentMessageRole
    content: str
    resource_refs: list[AgentResourceRef] = Field(default_factory=list)
    sequence: int
    created_at: datetime


class AgentConversationDetailRead(AgentConversationRead):
    messages: list[AgentMessageRead]
    message_page: PageInfo


class AgentStepRead(TimestampFields):
    id: str
    run_id: str
    sequence: int
    step_type: AgentStepType
    status: AgentStepStatus
    provider: str | None
    model: str | None
    api_shape: str | None
    attempt: int
    fallback_from: str | None
    fallback_reason: str | None
    latency_ms: int | None
    usage_json: str | None
    provider_request_id: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None


class AgentRunRead(TimestampFields):
    id: str
    conversation_id: str
    turn_id: str
    status: AgentRunStatus
    current_step_sequence: int
    model_call_count: int
    image_call_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None
    steps: list[AgentStepRead] = Field(default_factory=list)


class AgentTurnAcceptedRead(BaseModel):
    message: AgentMessageRead
    run: AgentRunRead
