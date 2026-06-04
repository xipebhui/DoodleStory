from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    ContentExtractionMediaKind,
    DownloadStatus,
    FileAssetPurpose,
    GenerationStepName,
    GeneratedImageStatus,
    GeneratedImageSourceType,
    GeneratedImageWorkflowStep,
    ImageCountMode,
    PanelType,
    PromptStatus,
    StepStatus,
    StorageBackend,
    StoryInputMode,
    StyleStatus,
    TaskStatus,
    UserRole,
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
    content_extractions: Mapped[list["ContentExtraction"]] = relationship(back_populates="owner")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


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
    style_prompt: Mapped[str] = mapped_column(Text)
    cover_asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

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
    style_id: Mapped[str] = mapped_column(ForeignKey("styles.id", ondelete="RESTRICT"), index=True)
    style_name_snapshot: Mapped[str] = mapped_column(String(80))
    style_prompt_snapshot: Mapped[str] = mapped_column(Text)
    image_model_name_snapshot: Mapped[str] = mapped_column(String(120))
    style_aspect_ratio_snapshot: Mapped[str] = mapped_column(String(20), default="9:16")
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

    owner: Mapped[User] = relationship(back_populates="tasks")
    style: Mapped[Style] = relationship(back_populates="tasks")
    steps: Mapped[list["GenerationStep"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    panels: Mapped[list["TaskPanel"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    characters: Mapped[list["TaskCharacter"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    generated_images: Mapped[list["GeneratedImage"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    downloads: Mapped[list["TaskDownload"]] = relationship(back_populates="task", cascade="all, delete-orphan")

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
                            "asset": appearance.reference_image,
                        }
                    )
        return references


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
        UniqueConstraint("panel_id", "generation_number"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="CASCADE"), index=True)
    panel_id: Mapped[str] = mapped_column(ForeignKey("task_panels.id", ondelete="CASCADE"), index=True)
    status: Mapped[GeneratedImageStatus] = mapped_column(Enum(GeneratedImageStatus), default=GeneratedImageStatus.queued)
    generation_number: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_type: Mapped[GeneratedImageSourceType] = mapped_column(Enum(GeneratedImageSourceType), default=GeneratedImageSourceType.initial, index=True)
    workflow_step: Mapped[Optional[GeneratedImageWorkflowStep]] = mapped_column(Enum(GeneratedImageWorkflowStep), nullable=True)
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
    panel: Mapped[TaskPanel] = relationship(back_populates="generated_images")
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
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    story_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    story_highlight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    story_summary_model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    story_summarized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    owner: Mapped[User] = relationship(back_populates="content_extractions")
    media: Mapped[list["ContentExtractionMedia"]] = relationship(back_populates="content_extraction", cascade="all, delete-orphan")


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
