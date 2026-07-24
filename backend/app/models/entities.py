from datetime import datetime
from enum import StrEnum
import json
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    AgentApprovalStatus,
    AgentApprovalType,
    AgentArtifactStatus,
    AgentArtifactType,
    AgentConversationStatus,
    AgentEventType,
    AgentMessageRole,
    AgentRunStatus,
    AgentStepStatus,
    AgentStepType,
    ContentExtractionMediaKind,
    CreditTransactionType,
    DownloadStatus,
    FileAssetPurpose,
    GenerationStepName,
    GeneratedImageStatus,
    GeneratedImageJobKind,
    GeneratedImageSourceType,
    GeneratedImageWorkflowStep,
    ImageCountMode,
    PanelType,
    PromptStatus,
    StepStatus,
    StorageBackend,
    StoryInputMode,
    StyleReferenceMode,
    StyleStatus,
    TaskStatus,
    UserRole,
    VideoTaskStatus,
    VideoTaskStepName,
    WorkflowStatus,
)


def new_id() -> str:
    return uuid4().hex


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    auth_provider_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    tasks: Mapped[list["GenerationTask"]] = relationship(back_populates="owner")
    video_tasks: Mapped[list["VideoTask"]] = relationship(back_populates="owner")
    content_extractions: Mapped[list["ContentExtraction"]] = relationship(back_populates="owner")
    user_characters: Mapped[list["UserCharacter"]] = relationship(back_populates="owner")
    audio_references: Mapped[list["AudioReference"]] = relationship(back_populates="owner")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    credit_account: Mapped[Optional["UserCreditAccount"]] = relationship(back_populates="user")
    credit_transactions: Mapped[list["CreditTransaction"]] = relationship(
        back_populates="user",
        foreign_keys="CreditTransaction.user_id",
    )
    agent_conversations: Mapped[list["AgentConversation"]] = relationship(back_populates="owner")
    decided_agent_approvals: Mapped[list["AgentApprovalRequest"]] = relationship()


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class Style(Base, TimestampMixin):
    __tablename__ = "styles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[StyleStatus] = mapped_column(Enum(StyleStatus), default=StyleStatus.draft, index=True)
    image_model_name: Mapped[str] = mapped_column(String(120), index=True)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="9:16")
    style_reference_mode: Mapped[StyleReferenceMode] = mapped_column(
        Enum(StyleReferenceMode), default=StyleReferenceMode.prompt, index=True
    )
    style_prompt: Mapped[str] = mapped_column(Text)
    cover_asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    cover_asset: Mapped[Optional["FileAsset"]] = relationship(foreign_keys=[cover_asset_id])
    reference_images: Mapped[list["StyleReferenceImage"]] = relationship(back_populates="style", cascade="all, delete-orphan")
    tests: Mapped[list["StyleTest"]] = relationship(back_populates="style")
    tasks: Mapped[list["GenerationTask"]] = relationship(back_populates="style")


class FileAsset(Base, TimestampMixin):
    __tablename__ = "file_assets"
    __table_args__ = (CheckConstraint("byte_size > 0", name="ck_file_assets_byte_size_positive"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    purpose: Mapped[FileAssetPurpose] = mapped_column(Enum(FileAssetPurpose), index=True)
    storage_backend: Mapped[StorageBackend] = mapped_column(Enum(StorageBackend), default=StorageBackend.local, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    public_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class StyleReferenceImage(Base):
    __tablename__ = "style_reference_images"
    __table_args__ = (UniqueConstraint("style_id", "asset_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    style_id: Mapped[str] = mapped_column(ForeignKey("styles.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("file_assets.id", ondelete="RESTRICT"))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    style: Mapped[Style] = relationship(back_populates="reference_images")
    asset: Mapped[FileAsset] = relationship()


class StyleTest(Base, TimestampMixin):
    __tablename__ = "style_tests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    style_id: Mapped[str] = mapped_column(ForeignKey("styles.id", ondelete="RESTRICT"), index=True)
    test_text: Mapped[str] = mapped_column(Text)
    style_prompt_snapshot: Mapped[str] = mapped_column(Text)
    image_model_name_snapshot: Mapped[str] = mapped_column(String(120))
    aspect_ratio_snapshot: Mapped[str] = mapped_column(String(20), default="9:16")
    style_reference_mode_snapshot: Mapped[StyleReferenceMode] = mapped_column(
        Enum(StyleReferenceMode), default=StyleReferenceMode.prompt
    )
    composed_prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus), default=WorkflowStatus.queued)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    cancel_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    output_asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_error_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    style: Mapped[Style] = relationship(back_populates="tests")
    output_asset: Mapped[Optional[FileAsset]] = relationship()


class UserCharacter(Base, TimestampMixin):
    __tablename__ = "user_characters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_asset_id: Mapped[str] = mapped_column(ForeignKey("file_assets.id", ondelete="RESTRICT"))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    owner: Mapped[User] = relationship(back_populates="user_characters")
    reference_asset: Mapped[FileAsset] = relationship()


class AudioReference(Base, TimestampMixin):
    __tablename__ = "audio_references"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("file_assets.id", ondelete="RESTRICT"))
    voice_provider: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    voice_model: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    voice_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    speech_speed: Mapped[float] = mapped_column(Float, default=1.0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    owner: Mapped[User] = relationship(back_populates="audio_references")
    asset: Mapped[FileAsset] = relationship()
    video_tasks: Mapped[list["VideoTask"]] = relationship(back_populates="audio_reference")


class GenerationTask(Base, TimestampMixin):
    __tablename__ = "generation_tasks"
    __table_args__ = (
        CheckConstraint(
            "(image_count_mode = 'auto' AND requested_image_count IS NULL) OR "
            "(image_count_mode = 'fixed' AND requested_image_count > 0)",
            name="ck_generation_tasks_image_count_mode",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    display_title: Mapped[str] = mapped_column(String(120))
    original_text: Mapped[str] = mapped_column(Text)
    story_input_mode: Mapped[StoryInputMode] = mapped_column(Enum(StoryInputMode), default=StoryInputMode.original)
    adapted_story_title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    adapted_story_hook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    adapted_story_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_count_mode: Mapped[ImageCountMode] = mapped_column(Enum(ImageCountMode))
    requested_image_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    use_character_references: Mapped[bool] = mapped_column(Boolean, default=False)
    last_panel_real_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    remove_image_text: Mapped[bool] = mapped_column(Boolean, default=False)
    style_id: Mapped[str] = mapped_column(ForeignKey("styles.id", ondelete="RESTRICT"), index=True)
    style_name_snapshot: Mapped[str] = mapped_column(String(80))
    style_prompt_snapshot: Mapped[str] = mapped_column(Text)
    image_model_name_snapshot: Mapped[str] = mapped_column(String(120))
    style_aspect_ratio_snapshot: Mapped[str] = mapped_column(String(20), default="9:16")
    style_reference_mode_snapshot: Mapped[StyleReferenceMode] = mapped_column(
        Enum(StyleReferenceMode), default=StyleReferenceMode.prompt
    )
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.queued, index=True)
    current_step: Mapped[Optional[GenerationStepName]] = mapped_column(Enum(GenerationStepName), nullable=True)
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    cancel_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_error_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    failure_alert_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    owner: Mapped[User] = relationship(back_populates="tasks")
    style: Mapped[Style] = relationship(back_populates="tasks")
    video_tasks: Mapped[list["VideoTask"]] = relationship(back_populates="source_task")
    steps: Mapped[list["GenerationStep"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    panels: Mapped[list["TaskPanel"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    characters: Mapped[list["TaskCharacter"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    style_reference_images: Mapped[list["TaskStyleReferenceImage"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    generated_images: Mapped[list["GeneratedImage"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    downloads: Mapped[list["TaskDownload"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="task")

    @property
    def character_references(self) -> list[dict[str, object]]:
        references: list[dict[str, object]] = []
        for character in sorted(self.characters, key=lambda item: item.character_key):
            for appearance in sorted(character.appearances, key=lambda item: item.appearance_key):
                if appearance.status == WorkflowStatus.succeeded and appearance.reference_image is not None:
                    references.append(
                        {
                            "id": appearance.id,
                            "name": character.name,
                            "age_stage": appearance.age_stage,
                            "reference_prompt": appearance.reference_prompt,
                            "asset": appearance.reference_image,
                        }
                    )
        return references


class TaskStyleReferenceImage(Base):
    __tablename__ = "task_style_reference_images"
    __table_args__ = (
        UniqueConstraint("task_id", "asset_id"),
        UniqueConstraint("task_id", "reference_order"),
        CheckConstraint("reference_order > 0", name="ck_task_style_reference_images_reference_order_positive"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("file_assets.id", ondelete="RESTRICT"))
    reference_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped[GenerationTask] = relationship(back_populates="style_reference_images")
    asset: Mapped[FileAsset] = relationship()


class GenerationStep(Base, TimestampMixin):
    __tablename__ = "generation_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="CASCADE"), index=True)
    step_name: Mapped[GenerationStepName] = mapped_column(Enum(GenerationStepName), index=True)
    status: Mapped[StepStatus] = mapped_column(Enum(StepStatus), default=StepStatus.queued, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    output_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_error_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    task: Mapped[GenerationTask] = relationship(back_populates="steps")


class TaskPanel(Base, TimestampMixin):
    __tablename__ = "task_panels"
    __table_args__ = (
        UniqueConstraint("task_id", "panel_order"),
        CheckConstraint("panel_order > 0", name="ck_task_panels_panel_order_positive"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="CASCADE"), index=True)
    panel_order: Mapped[int] = mapped_column(Integer)
    panel_type: Mapped[PanelType] = mapped_column(Enum(PanelType), default=PanelType.scene, index=True)
    original_text_segment: Mapped[str] = mapped_column(Text)
    narration_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dialogue_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_text_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_layout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_status: Mapped[PromptStatus] = mapped_column(Enum(PromptStatus), default=PromptStatus.pending)
    generated_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_model_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    task: Mapped[GenerationTask] = relationship(back_populates="panels")
    generated_images: Mapped[list["GeneratedImage"]] = relationship(back_populates="panel", cascade="all, delete-orphan")
    character_appearances: Mapped[list["TaskPanelCharacterAppearance"]] = relationship(back_populates="panel", cascade="all, delete-orphan")


class TaskCharacter(Base, TimestampMixin):
    __tablename__ = "task_characters"
    __table_args__ = (UniqueConstraint("task_id", "character_key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="CASCADE"), index=True)
    character_key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    importance: Mapped[str] = mapped_column(String(40), default="primary")

    task: Mapped[GenerationTask] = relationship(back_populates="characters")
    appearances: Mapped[list["TaskCharacterAppearance"]] = relationship(back_populates="character", cascade="all, delete-orphan")


class TaskCharacterAppearance(Base, TimestampMixin):
    __tablename__ = "task_character_appearances"
    __table_args__ = (UniqueConstraint("task_character_id", "appearance_key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_character_id: Mapped[str] = mapped_column(ForeignKey("task_characters.id", ondelete="CASCADE"), index=True)
    appearance_key: Mapped[str] = mapped_column(String(100))
    age_stage: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    visual_prompt: Mapped[str] = mapped_column(Text)
    reference_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_image_id: Mapped[Optional[str]] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus), default=WorkflowStatus.queued, index=True)
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    character: Mapped[TaskCharacter] = relationship(back_populates="appearances")
    reference_image: Mapped[Optional[FileAsset]] = relationship()
    panel_links: Mapped[list["TaskPanelCharacterAppearance"]] = relationship(back_populates="appearance", cascade="all, delete-orphan")


class TaskPanelCharacterAppearance(Base):
    __tablename__ = "task_panel_character_appearances"
    __table_args__ = (
        UniqueConstraint("panel_id", "task_character_appearance_id"),
        UniqueConstraint("panel_id", "reference_order"),
        CheckConstraint("reference_order > 0", name="ck_task_panel_character_appearances_reference_order_positive"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    panel_id: Mapped[str] = mapped_column(ForeignKey("task_panels.id", ondelete="CASCADE"), index=True)
    task_character_appearance_id: Mapped[str] = mapped_column(ForeignKey("task_character_appearances.id", ondelete="CASCADE"), index=True)
    reference_order: Mapped[int] = mapped_column(Integer)
    usage_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    panel: Mapped[TaskPanel] = relationship(back_populates="character_appearances")
    appearance: Mapped[TaskCharacterAppearance] = relationship(back_populates="panel_links")


class GeneratedImage(Base, TimestampMixin):
    __tablename__ = "generated_images"
    __table_args__ = (
        CheckConstraint("status != 'succeeded' OR asset_id IS NOT NULL", name="ck_generated_images_succeeded_asset"),
        CheckConstraint("generation_number > 0", name="ck_generated_images_generation_number_positive"),
        CheckConstraint("job_kind != 'panel_image' OR panel_id IS NOT NULL", name="ck_generated_images_panel_job_panel"),
        CheckConstraint(
            "job_kind != 'character_reference' OR character_appearance_id IS NOT NULL",
            name="ck_generated_images_character_job_appearance",
        ),
        UniqueConstraint("panel_id", "generation_number"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="CASCADE"), index=True)
    panel_id: Mapped[Optional[str]] = mapped_column(ForeignKey("task_panels.id", ondelete="CASCADE"), nullable=True, index=True)
    character_appearance_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("task_character_appearances.id", ondelete="CASCADE"), nullable=True, index=True
    )
    owner_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    job_kind: Mapped[GeneratedImageJobKind] = mapped_column(
        Enum(GeneratedImageJobKind), default=GeneratedImageJobKind.panel_image, index=True
    )
    status: Mapped[GeneratedImageStatus] = mapped_column(Enum(GeneratedImageStatus), default=GeneratedImageStatus.queued)
    generation_number: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_type: Mapped[GeneratedImageSourceType] = mapped_column(Enum(GeneratedImageSourceType), default=GeneratedImageSourceType.initial, index=True)
    workflow_step: Mapped[Optional[GeneratedImageWorkflowStep]] = mapped_column(Enum(GeneratedImageWorkflowStep), nullable=True)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    lease_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    queue_group: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    user_instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    previous_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_text_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_layout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_model_snapshot: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    final_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_model_name_snapshot: Mapped[str] = mapped_column(String(120))
    asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_error_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    task: Mapped[GenerationTask] = relationship(back_populates="generated_images")
    panel: Mapped[Optional[TaskPanel]] = relationship(back_populates="generated_images")
    character_appearance: Mapped[Optional[TaskCharacterAppearance]] = relationship()
    asset: Mapped[Optional[FileAsset]] = relationship()


class TaskDownload(Base, TimestampMixin):
    __tablename__ = "task_downloads"
    __table_args__ = (
        CheckConstraint("status != 'ready' OR asset_id IS NOT NULL", name="ck_task_downloads_ready_asset"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="CASCADE"), index=True)
    status: Mapped[DownloadStatus] = mapped_column(Enum(DownloadStatus), default=DownloadStatus.queued, index=True)
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_error_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    task: Mapped[GenerationTask] = relationship(back_populates="downloads")
    asset: Mapped[Optional[FileAsset]] = relationship()


class VideoTask(Base, TimestampMixin):
    __tablename__ = "video_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    source_task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="RESTRICT"), unique=True, index=True)
    audio_reference_id: Mapped[str] = mapped_column(ForeignKey("audio_references.id", ondelete="RESTRICT"), index=True)
    display_title: Mapped[str] = mapped_column(String(120))
    original_text: Mapped[str] = mapped_column(Text)
    audio_reference_name_snapshot: Mapped[str] = mapped_column(String(120))
    audio_reference_text_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_reference_asset_id_snapshot: Mapped[str] = mapped_column(ForeignKey("file_assets.id", ondelete="RESTRICT"))
    voice_provider_snapshot: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    voice_model_snapshot: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    voice_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    voice_speed_snapshot: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[VideoTaskStatus] = mapped_column(
        Enum(VideoTaskStatus), default=VideoTaskStatus.waiting_for_images, index=True
    )
    current_step: Mapped[VideoTaskStepName] = mapped_column(
        Enum(VideoTaskStepName), default=VideoTaskStepName.generate_source_images, index=True
    )
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=4)
    narration_audio_asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    output_video_asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    video_provider_job_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    video_provider_status: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    video_provider_output_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    video_episode_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    video_provider_result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_error_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    owner: Mapped[User] = relationship(back_populates="video_tasks")
    source_task: Mapped[GenerationTask] = relationship(back_populates="video_tasks")
    audio_reference: Mapped[AudioReference] = relationship(back_populates="video_tasks")
    audio_reference_asset_snapshot: Mapped[FileAsset] = relationship(foreign_keys=[audio_reference_asset_id_snapshot])
    narration_audio_asset: Mapped[Optional[FileAsset]] = relationship(foreign_keys=[narration_audio_asset_id])
    output_video_asset: Mapped[Optional[FileAsset]] = relationship(foreign_keys=[output_video_asset_id])
    audio_segments: Mapped[list["VideoTaskAudioSegment"]] = relationship(
        back_populates="video_task", cascade="all, delete-orphan"
    )


class VideoTaskAudioSegment(Base, TimestampMixin):
    __tablename__ = "video_task_audio_segments"
    __table_args__ = (
        UniqueConstraint("video_task_id", "panel_id"),
        CheckConstraint("panel_order > 0", name="ck_video_task_audio_segments_panel_order_positive"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    video_task_id: Mapped[str] = mapped_column(ForeignKey("video_tasks.id", ondelete="CASCADE"), index=True)
    panel_id: Mapped[str] = mapped_column(ForeignKey("task_panels.id", ondelete="CASCADE"), index=True)
    panel_order: Mapped[int] = mapped_column(Integer)
    narration_text: Mapped[str] = mapped_column(Text)
    asset_id: Mapped[str] = mapped_column(ForeignKey("file_assets.id", ondelete="RESTRICT"))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    video_task: Mapped[VideoTask] = relationship(back_populates="audio_segments")
    panel: Mapped[TaskPanel] = relationship()
    asset: Mapped[FileAsset] = relationship()


class ContentExtraction(Base, TimestampMixin):
    __tablename__ = "content_extractions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    raw_input: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(1000), index=True)
    media_type: Mapped[str] = mapped_column(String(40), index=True)
    aweme_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    output_dir: Mapped[str] = mapped_column(String(1000))
    manifest_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_tags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(40), default="succeeded", index=True)
    processing_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    story_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    story_highlight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    story_summary_model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    story_summarized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    linked_task_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("generation_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_create_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    task_create_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owner: Mapped[User] = relationship(back_populates="content_extractions")
    media: Mapped[list["ContentExtractionMedia"]] = relationship(back_populates="content_extraction", cascade="all, delete-orphan")
    linked_task: Mapped[Optional[GenerationTask]] = relationship(foreign_keys=[linked_task_id])

    @property
    def source_tags(self) -> list[str]:
        if not self.source_tags_json:
            return []
        tags = json.loads(self.source_tags_json)
        if not isinstance(tags, list) or any(not isinstance(item, str) for item in tags):
            raise ValueError("content_extractions.source_tags_json 必须是字符串数组 JSON")
        return tags


class ContentExtractionMedia(Base, TimestampMixin):
    __tablename__ = "content_extraction_media"
    __table_args__ = (
        CheckConstraint("display_order > 0", name="ck_content_extraction_media_display_order_positive"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    content_extraction_id: Mapped[str] = mapped_column(ForeignKey("content_extractions.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("file_assets.id", ondelete="RESTRICT"), index=True)
    source_path: Mapped[str] = mapped_column(String(1000))
    media_kind: Mapped[ContentExtractionMediaKind] = mapped_column(Enum(ContentExtractionMediaKind), index=True)
    display_order: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    content_extraction: Mapped[ContentExtraction] = relationship(back_populates="media")
    asset: Mapped[FileAsset] = relationship()


class UserCreditAccount(Base, TimestampMixin):
    __tablename__ = "user_credit_accounts"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_user_credit_accounts_balance_non_negative"),
        CheckConstraint("reserved_balance >= 0", name="ck_user_credit_accounts_reserved_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    reserved_balance: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="credit_account")


class CreditTransaction(Base, TimestampMixin):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        CheckConstraint("amount != 0", name="ck_credit_transactions_amount_non_zero"),
        CheckConstraint("balance_after >= 0", name="ck_credit_transactions_balance_after_non_negative"),
        CheckConstraint("reserved_balance_after >= 0", name="ck_credit_transactions_reserved_after_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    transaction_type: Mapped[CreditTransactionType] = mapped_column(Enum(CreditTransactionType), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    balance_before: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    reserved_balance_before: Mapped[int] = mapped_column(Integer)
    reserved_balance_after: Mapped[int] = mapped_column(Integer)
    admin_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id: Mapped[Optional[str]] = mapped_column(ForeignKey("generation_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    panel_id: Mapped[Optional[str]] = mapped_column(ForeignKey("task_panels.id", ondelete="SET NULL"), nullable=True, index=True)
    generated_image_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("generated_images.id", ondelete="SET NULL"), nullable=True, index=True
    )
    style_test_id: Mapped[Optional[str]] = mapped_column(ForeignKey("style_tests.id", ondelete="SET NULL"), nullable=True, index=True)
    character_appearance_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("task_character_appearances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    activation_code_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("credit_activation_codes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="credit_transactions", foreign_keys=[user_id])
    admin_user: Mapped[Optional[User]] = relationship(foreign_keys=[admin_user_id])


class CreditActivationCode(Base, TimestampMixin):
    __tablename__ = "credit_activation_codes"
    __table_args__ = (
        CheckConstraint("credit_amount > 0", name="ck_credit_activation_codes_credit_amount_positive"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_prefix: Mapped[str] = mapped_column(String(12), index=True)
    credit_amount: Mapped[int] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by_admin_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    redeemed_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by_admin: Mapped[Optional[User]] = relationship(foreign_keys=[created_by_admin_id])
    redeemed_by_user: Mapped[Optional[User]] = relationship(foreign_keys=[redeemed_by_user_id])
    redemptions: Mapped[list["CreditActivationCodeRedemption"]] = relationship(
        back_populates="activation_code",
        cascade="all, delete-orphan",
    )


class CreditActivationCodeRedemption(Base, TimestampMixin):
    __tablename__ = "credit_activation_code_redemptions"
    __table_args__ = (UniqueConstraint("activation_code_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    activation_code_id: Mapped[str] = mapped_column(ForeignKey("credit_activation_codes.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("credit_transactions.id", ondelete="RESTRICT"), unique=True)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    activation_code: Mapped[CreditActivationCode] = relationship(back_populates="redemptions")
    user: Mapped[User] = relationship()
    transaction: Mapped[CreditTransaction] = relationship()


class AgentConversation(Base, TimestampMixin):
    __tablename__ = "agent_conversations"
    __table_args__ = (
        Index("ix_agent_conversations_owner_last_message", "owner_user_id", "last_message_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[AgentConversationStatus] = mapped_column(
        Enum(AgentConversationStatus), default=AgentConversationStatus.active, index=True
    )
    last_message_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    owner: Mapped[User] = relationship(back_populates="agent_conversations")
    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["AgentArtifact"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    approval_requests: Mapped[list["AgentApprovalRequest"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    events: Mapped[list["AgentEvent"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence", name="uq_agent_messages_conversation_sequence"),
        CheckConstraint("sequence > 0", name="ck_agent_messages_sequence_positive"),
        Index("ix_agent_messages_conversation_sequence", "conversation_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    turn_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    role: Mapped[AgentMessageRole] = mapped_column(Enum(AgentMessageRole), index=True)
    content: Mapped[str] = mapped_column(Text)
    resource_refs_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped[AgentConversation] = relationship(back_populates="messages")


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("conversation_id", "turn_id", name="uq_agent_runs_conversation_turn"),
        Index("ix_agent_runs_status_updated", "status", "updated_at"),
        Index("ix_agent_runs_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    turn_id: Mapped[str] = mapped_column(String(32), index=True)
    task_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("generation_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[AgentRunStatus] = mapped_column(Enum(AgentRunStatus), default=AgentRunStatus.queued, index=True)
    current_step_sequence: Mapped[int] = mapped_column(Integer, default=0)
    model_call_count: Mapped[int] = mapped_column(Integer, default=0)
    image_call_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_error_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    conversation: Mapped[AgentConversation] = relationship(back_populates="runs")
    task: Mapped[Optional[GenerationTask]] = relationship(back_populates="agent_runs")
    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["AgentArtifact"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    approval_requests: Mapped[list["AgentApprovalRequest"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    events: Mapped[list["AgentEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AgentStep(Base, TimestampMixin):
    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_steps_run_sequence"),
        UniqueConstraint("idempotency_key", name="uq_agent_steps_idempotency_key"),
        CheckConstraint("sequence > 0", name="ck_agent_steps_sequence_positive"),
        CheckConstraint("attempt > 0", name="ck_agent_steps_attempt_positive"),
        Index("ix_agent_steps_run_sequence", "run_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[AgentStepType] = mapped_column(Enum(AgentStepType), index=True)
    status: Mapped[AgentStepStatus] = mapped_column(Enum(AgentStepStatus), default=AgentStepStatus.pending, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    api_shape: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    fallback_from: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    fallback_reason: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    usage_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    input_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_error_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    run: Mapped[AgentRun] = relationship(back_populates="steps")


class AgentArtifact(Base, TimestampMixin):
    __tablename__ = "agent_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "artifact_type",
            "version",
            name="uq_agent_artifacts_run_type_version",
        ),
        CheckConstraint("version > 0", name="ck_agent_artifacts_version_positive"),
        Index("ix_agent_artifacts_run_type_version", "run_id", "artifact_type", "version"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[AgentArtifactType] = mapped_column(Enum(AgentArtifactType))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[AgentArtifactStatus] = mapped_column(
        Enum(AgentArtifactStatus), default=AgentArtifactStatus.draft
    )
    content_json: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(80))

    conversation: Mapped[AgentConversation] = relationship(back_populates="artifacts")
    run: Mapped[AgentRun] = relationship(back_populates="artifacts")
    approval_request: Mapped[Optional["AgentApprovalRequest"]] = relationship(
        back_populates="artifact", uselist=False
    )


class AgentApprovalRequest(Base):
    __tablename__ = "agent_approval_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("agent_artifacts.id", ondelete="CASCADE"), unique=True
    )
    artifact_hash: Mapped[str] = mapped_column(String(80))
    approval_type: Mapped[AgentApprovalType] = mapped_column(Enum(AgentApprovalType))
    status: Mapped[AgentApprovalStatus] = mapped_column(
        Enum(AgentApprovalStatus), default=AgentApprovalStatus.pending, index=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    decided_by_user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    conversation: Mapped[AgentConversation] = relationship(back_populates="approval_requests")
    run: Mapped[AgentRun] = relationship(back_populates="approval_requests")
    artifact: Mapped[AgentArtifact] = relationship(back_populates="approval_request")


class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_events_run_sequence"),
        CheckConstraint("sequence > 0", name="ck_agent_events_sequence_positive"),
        Index(
            "ix_agent_events_conversation_created_sequence",
            "conversation_id",
            "created_at",
            "sequence",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[AgentEventType] = mapped_column(
        Enum(
            AgentEventType,
            values_callable=lambda enum_type: [item.value for item in enum_type],
        )
    )
    public_payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped[AgentConversation] = relationship(back_populates="events")
    run: Mapped[AgentRun] = relationship(back_populates="events")
