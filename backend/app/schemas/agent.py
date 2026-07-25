from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    AgentApprovalStatus,
    AgentArtifactStatus,
    AgentArtifactType,
    AgentConversationStatus,
    AgentMessageRole,
    AgentRunStatus,
    AgentStepStatus,
    AgentStepType,
    GeneratedImageStatus,
    GeneratedImageSourceType,
    TaskStatus,
)
from app.schemas.common import OrmModel, PageInfo, TimestampFields


class AgentResourceKind(StrEnum):
    style = "style"
    character = "character"
    task = "task"
    panel = "panel"
    image_version = "image_version"


class AgentResourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AgentResourceKind
    id: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=160)
    safe_summary: dict[str, object] | None = None


class AgentResourceOption(BaseModel):
    kind: AgentResourceKind
    id: str
    display_name: str
    secondary_text: str | None = None
    parent_id: str | None = None
    status: str | None = None


class ComicPlanPanel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    panel_key: str = Field(pattern=r"^panel-[1-8]$")
    story_beat: str = Field(min_length=1, max_length=500)
    visual_goal: str = Field(min_length=1, max_length=800)
    image_prompt: str = Field(min_length=1, max_length=3000)
    required_text: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("story_beat", "visual_goal", "image_prompt")
    @classmethod
    def strip_required_text_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("ComicPlan 文本字段不能为空")
        return cleaned

    @field_validator("required_text")
    @classmethod
    def validate_required_text(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item or len(item) > 120 for item in cleaned):
            raise ValueError("图片内文字必须是 1 到 120 字的非空文本")
        return cleaned


class ComicPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, ge=1, le=1)
    title: str = Field(min_length=1, max_length=120)
    story_summary: str = Field(min_length=1, max_length=800)
    aspect_ratio: str = Field(min_length=1, max_length=40)
    style_ref_id: str = Field(min_length=1, max_length=32)
    panels: list[ComicPlanPanel] = Field(min_length=2, max_length=8)
    estimated_image_credits: int = Field(ge=2, le=8)

    @field_validator("title", "story_summary", "aspect_ratio", "style_ref_id")
    @classmethod
    def strip_plan_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("ComicPlan 标题和概要不能为空")
        return cleaned

    @field_validator("panels")
    @classmethod
    def validate_panel_keys(cls, value: list[ComicPlanPanel]) -> list[ComicPlanPanel]:
        expected = [f"panel-{index}" for index in range(1, len(value) + 1)]
        if [panel.panel_key for panel in value] != expected:
            raise ValueError("ComicPlan Panel key 必须从 panel-1 开始连续编号")
        normalized_beats = [" ".join(panel.story_beat.split()).casefold() for panel in value]
        if len(set(normalized_beats)) != len(normalized_beats):
            raise ValueError("ComicPlan 不允许完全重复的 story beat")
        return value

    @model_validator(mode="after")
    def validate_budget(self) -> "ComicPlan":
        if self.estimated_image_credits != len(self.panels):
            raise ValueError("预计图片积分必须等于 Panel 数量")
        return self


class AgentApprovalRead(BaseModel):
    id: str
    artifact_id: str
    status: AgentApprovalStatus
    artifact_hash: str
    feedback: str | None
    requested_at: datetime
    resolved_at: datetime | None


class AgentArtifactRead(TimestampFields):
    id: str
    conversation_id: str
    run_id: str
    artifact_type: AgentArtifactType
    version: int
    status: AgentArtifactStatus
    content_hash: str
    content: ComicPlan
    approval: AgentApprovalRead | None


class AgentApprovalDecision(BaseModel):
    decision: str = Field(pattern=r"^(approve|request_changes)$")
    feedback: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_feedback(self) -> "AgentApprovalDecision":
        if self.decision == "request_changes":
            if self.feedback is None or not self.feedback.strip():
                raise ValueError("提出修改时必须填写反馈")
            self.feedback = self.feedback.strip()
        elif self.feedback is not None:
            self.feedback = None
        return self


class AgentEventRead(BaseModel):
    id: str
    conversation_id: str
    run_id: str
    sequence: int
    event_type: str
    payload: dict[str, object]
    created_at: datetime


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


class AgentTaskCardImageRead(BaseModel):
    id: str
    status: GeneratedImageStatus
    asset_id: str | None
    width: int | None
    height: int | None
    error_code: str | None
    error_message: str | None


class AgentTaskCardPanelRead(BaseModel):
    id: str
    panel_order: int
    story_beat: str
    visual_goal: str | None
    image: AgentTaskCardImageRead | None


class AgentTaskCardRead(BaseModel):
    task_id: str
    run_id: str
    title: str
    status: TaskStatus
    progress_current: int
    progress_total: int
    error_code: str | None
    error_message: str | None
    panels: list[AgentTaskCardPanelRead]


class AgentTaskInspectorImageRead(BaseModel):
    id: str
    generation_number: int
    status: GeneratedImageStatus
    is_current: bool
    source_type: GeneratedImageSourceType
    asset_id: str | None
    width: int | None
    height: int | None
    error_code: str | None
    error_message: str | None
    accepted_at: datetime | None
    accepted_by_current_user: bool
    inspection: "AgentImageInspectionRead | None" = None
    created_at: datetime


class AgentImageInspectionIssueRead(BaseModel):
    code: str
    message: str
    suggested_change: str | None = None


class AgentImageInspectionRead(BaseModel):
    verdict: Literal["accept", "revise", "ask_user", "blocked"]
    scores: dict[str, float]
    issues: list[AgentImageInspectionIssueRead] = Field(default_factory=list)
    provider: str
    model: str
    inspected_at: datetime


class AgentPanelRegenerationCreate(BaseModel):
    instruction: str = Field(min_length=1, max_length=4_000)
    source_image_version_id: str
    expected_credit_cost: Literal[1]
    allow_auto_revision: bool = False


class AgentTaskInspectorPanelRead(BaseModel):
    id: str
    panel_order: int
    story_beat: str
    visual_goal: str | None
    status: GeneratedImageStatus | None
    error_code: str | None
    error_message: str | None
    current_image: AgentTaskInspectorImageRead | None
    versions: list[AgentTaskInspectorImageRead] = Field(default_factory=list)


class AgentTaskInspectorRead(BaseModel):
    conversation_id: str
    task_id: str
    title: str
    status: TaskStatus
    progress_current: int
    progress_total: int
    error_code: str | None
    error_message: str | None
    panels: list[AgentTaskInspectorPanelRead] = Field(default_factory=list)


class AgentRunSummaryRead(TimestampFields):
    id: str
    turn_id: str
    task_id: str | None
    status: AgentRunStatus
    model_call_count: int
    image_call_count: int
    error_code: str | None
    error_message: str | None


class AgentConversationDetailRead(AgentConversationRead):
    messages: list[AgentMessageRead]
    message_page: PageInfo
    task_cards: list[AgentTaskCardRead] = Field(default_factory=list)
    runs: list[AgentRunSummaryRead] = Field(default_factory=list)


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
    task_id: str | None
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
