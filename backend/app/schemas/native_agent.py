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
    model_route: Literal["huomiao_responses", "siliconflow_chat_v1"] | None = None
    style_id: str | None = Field(default=None, max_length=32)
    creation_channel_id: str | None = Field(default=None, max_length=32)
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


class NativeAgentFollowUpCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=20_000)
    idempotency_key: str = Field(min_length=8, max_length=160)

    @field_validator("content", "idempotency_key")
    @classmethod
    def normalize_follow_up_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


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
    provider: str
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
    model_call_id: str | None
    model_provider: str | None
    model_api_shape: str | None
    model_name: str | None
    provider_response_id: str | None
    execution_attempt: int | None
    model_call_ordinal: int | None
    converted_message_count: int | None
    latency_ms: int | None
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


class NativeAgentArticleApprovalRead(BaseModel):
    id: str
    status: Literal[
        "pending",
        "approved",
        "changes_requested",
        "cancelled",
    ]
    feedback: str | None
    requested_at: datetime
    resolved_at: datetime | None


class NativeAgentArtifactRead(BaseModel):
    id: str
    artifact_type: Literal[
        "topic_candidates",
        "article_draft",
        "article_review",
        "final_article",
    ]
    schema_version: int
    version: int
    status: Literal[
        "completed",
        "awaiting_approval",
        "approved",
        "rejected",
        "superseded",
    ]
    producer_role: str
    content: dict[str, object]
    content_hash: str
    approval: NativeAgentArticleApprovalRead | None
    created_at: datetime
    updated_at: datetime


class NativeAgentArticleApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "changes_requested"]
    feedback: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_feedback(self) -> "NativeAgentArticleApprovalDecision":
        if self.decision == "changes_requested" and not (
            self.feedback and self.feedback.strip()
        ):
            raise ValueError("要求修改时必须填写具体意见")
        return self


class DurableVisualPlanPanelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    panel_key: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=20_000)
    title: str | None = Field(default=None, max_length=240)
    quality_criteria: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("panel_key", "prompt")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class DurableVisualPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    panels: list[DurableVisualPlanPanelInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_unique_panel_keys(self) -> "DurableVisualPlanCreate":
        keys = [panel.panel_key for panel in self.panels]
        if len(keys) != len(set(keys)):
            raise ValueError("panel_key 不能重复")
        return self


class DurableGateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "changes_requested"]
    feedback: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_feedback(self) -> "DurableGateDecision":
        if self.decision == "changes_requested" and not (
            self.feedback and self.feedback.strip()
        ):
            raise ValueError("要求修改时必须填写具体意见")
        return self


class DurableControlCommandCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal[
        "approve_gate",
        "request_changes",
        "retry_task",
        "cancel_run",
        "resume_run",
        "resolve_unknown_effect",
    ]
    idempotency_key: str = Field(min_length=8, max_length=160)
    expected_state_version: int = Field(ge=1)
    target_id: str | None = Field(default=None, max_length=32)
    feedback: str | None = Field(default=None, max_length=4000)
    resolution: Literal["succeeded", "failed"] | None = None
    result_ref: dict[str, object] | None = None

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 8:
            raise ValueError("idempotency_key 不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_command_payload(self) -> "DurableControlCommandCreate":
        if self.command in {"request_changes", "cancel_run"} and not (
            self.feedback and self.feedback.strip()
        ):
            raise ValueError("修改或取消命令必须填写具体原因")
        if self.command in {
            "retry_task",
            "resolve_unknown_effect",
        } and not self.target_id:
            raise ValueError("当前命令必须指定 target_id")
        if self.command == "resolve_unknown_effect":
            if self.resolution is None:
                raise ValueError("处理 unknown Effect 必须指定 resolution")
            if self.resolution == "succeeded" and not self.result_ref:
                raise ValueError("将 unknown Effect 标记成功必须提供 result_ref")
        elif self.resolution is not None or self.result_ref is not None:
            raise ValueError("只有 resolve_unknown_effect 可以提供 resolution/result_ref")
        return self


class DurableControlStateRead(BaseModel):
    workflow_id: str
    status: str
    state_version: int
    current_checkpoint_id: str | None
    current_gate_id: str | None
    expected_input_kind: str | None
    allowed_actions: list[str]
    tasks: list[dict[str, object]]
    unknown_effects: list[dict[str, object]]


class DurableControlCommandRead(BaseModel):
    id: str
    command: str
    target_id: str | None
    idempotency_key: str
    expected_state_version: int
    status: str
    result: dict[str, object]
    control_state: DurableControlStateRead
    created_at: datetime


class DurableImageQualityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["accepted", "changes_required", "blocked", "unknown"]
    summary: str = Field(min_length=1, max_length=2000)
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("质量结论摘要不能为空")
        return normalized


class DurablePanelRerunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: str = Field(min_length=1, max_length=4000)

    @field_validator("feedback")
    @classmethod
    def normalize_feedback(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("局部重跑必须填写具体意见")
        return normalized


class NativeAgentRunRead(BaseModel):
    id: str
    conversation_id: str
    parent_run_id: str | None
    continued_from_checkpoint_id: str | None
    skill_version_id: str
    skill_name: str
    skill_version: int
    style_id: str | None
    style_name: str | None
    creation_channel_id: str | None
    creation_channel_name: str | None
    youtube_channel_id: str | None
    youtube_channel_name: str | None
    youtube_publishable_video_id: str | None
    youtube_publishable_video_title: str | None
    youtube_publish_confirmation: dict[str, object] | None
    status: AgentRunStatus
    model_route: str
    model_provider: str
    model_api_shape: str
    model: str
    model_call_count: int
    image_call_count: int
    speech_call_count: int
    subtitle_call_count: int
    video_call_count: int
    workflow_phase: str | None
    workflow_revision: int
    workflow_checkpoint: dict[str, object] | None
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
    artifacts: list[NativeAgentArtifactRead] = Field(default_factory=list)
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
            "get_account_creation_context",
            "inspect_youtube_channel",
            "write_article",
            "review_article",
            "submit_final_article",
        ]
    ]
    image_review: Literal["native_model_vision"]
