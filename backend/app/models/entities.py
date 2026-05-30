from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    FileAssetPurpose,
    GeneratedImageStatus,
    ImageCountMode,
    PromptStatus,
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

    tasks: Mapped[list["GenerationTask"]] = relationship(back_populates="owner")


class Style(Base, TimestampMixin):
    __tablename__ = "styles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[StyleStatus] = mapped_column(Enum(StyleStatus), default=StyleStatus.draft, index=True)
    generation_profile_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    style_prompt: Mapped[str] = mapped_column(Text)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    reference_images: Mapped[list["StyleReferenceImage"]] = relationship(back_populates="style", cascade="all, delete-orphan")
    tests: Mapped[list["StyleTest"]] = relationship(back_populates="style")
    tasks: Mapped[list["GenerationTask"]] = relationship(back_populates="style")


class FileAsset(Base, TimestampMixin):
    __tablename__ = "file_assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    purpose: Mapped[FileAssetPurpose] = mapped_column(Enum(FileAssetPurpose), index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
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
    generation_profile_key_snapshot: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    composed_prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus), default=WorkflowStatus.queued)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    style: Mapped[Style] = relationship(back_populates="tests")


class GenerationTask(Base, TimestampMixin):
    __tablename__ = "generation_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    display_title: Mapped[str] = mapped_column(String(120))
    original_text: Mapped[str] = mapped_column(Text)
    image_count_mode: Mapped[ImageCountMode] = mapped_column(Enum(ImageCountMode))
    requested_image_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    style_id: Mapped[str] = mapped_column(ForeignKey("styles.id", ondelete="RESTRICT"), index=True)
    style_name_snapshot: Mapped[str] = mapped_column(String(80))
    style_prompt_snapshot: Mapped[str] = mapped_column(Text)
    generation_profile_key_snapshot: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.queued, index=True)
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owner: Mapped[User] = relationship(back_populates="tasks")
    style: Mapped[Style] = relationship(back_populates="tasks")
    panels: Mapped[list["TaskPanel"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskPanel(Base, TimestampMixin):
    __tablename__ = "task_panels"
    __table_args__ = (UniqueConstraint("task_id", "panel_order"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="CASCADE"), index=True)
    panel_order: Mapped[int] = mapped_column(Integer)
    original_text_segment: Mapped[str] = mapped_column(Text)
    prompt_status: Mapped[PromptStatus] = mapped_column(Enum(PromptStatus), default=PromptStatus.pending)
    generated_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    task: Mapped[GenerationTask] = relationship(back_populates="panels")
    generated_image: Mapped[Optional["GeneratedImage"]] = relationship(back_populates="panel")


class GeneratedImage(Base, TimestampMixin):
    __tablename__ = "generated_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("generation_tasks.id", ondelete="CASCADE"), index=True)
    panel_id: Mapped[str] = mapped_column(ForeignKey("task_panels.id", ondelete="CASCADE"), unique=True)
    status: Mapped[GeneratedImageStatus] = mapped_column(Enum(GeneratedImageStatus), default=GeneratedImageStatus.queued)
    final_prompt: Mapped[str] = mapped_column(Text)
    generation_profile_key_snapshot: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("file_assets.id", ondelete="SET NULL"), nullable=True)

    panel: Mapped[TaskPanel] = relationship(back_populates="generated_image")
    asset: Mapped[Optional[FileAsset]] = relationship()
