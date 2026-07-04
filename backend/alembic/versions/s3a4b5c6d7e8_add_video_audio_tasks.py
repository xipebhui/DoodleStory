"""add video and audio task tables

Revision ID: s3a4b5c6d7e8
Revises: r2f3a4b5c6d7
Create Date: 2026-06-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s3a4b5c6d7e8"
down_revision: Union[str, None] = "r2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


video_task_status = sa.Enum(
    "waiting_for_images",
    "ready_for_audio",
    "audio_generating",
    "audio_ready",
    "video_generating",
    "succeeded",
    "failed",
    "cancel_requested",
    "cancelled",
    name="videotaskstatus",
)

video_task_step_name = sa.Enum(
    "generate_source_images",
    "generate_narration_audio",
    "submit_video",
    "download_video",
    name="videotaskstepname",
)


def upgrade() -> None:
    op.create_table(
        "audio_references",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_text", sa.Text(), nullable=True),
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("voice_provider", sa.String(length=80), nullable=True),
        sa.Column("voice_model", sa.String(length=160), nullable=True),
        sa.Column("voice_name", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["file_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audio_references_deleted_at"), "audio_references", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_audio_references_owner_user_id"), "audio_references", ["owner_user_id"], unique=False)

    op.create_table(
        "video_tasks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("source_task_id", sa.String(length=32), nullable=False),
        sa.Column("audio_reference_id", sa.String(length=32), nullable=False),
        sa.Column("display_title", sa.String(length=120), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("audio_reference_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("audio_reference_text_snapshot", sa.Text(), nullable=True),
        sa.Column("audio_reference_asset_id_snapshot", sa.String(length=32), nullable=False),
        sa.Column("status", video_task_status, nullable=False),
        sa.Column("current_step", video_task_step_name, nullable=False),
        sa.Column("progress_current", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("narration_audio_asset_id", sa.String(length=32), nullable=True),
        sa.Column("output_video_asset_id", sa.String(length=32), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("internal_error_ref", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["audio_reference_asset_id_snapshot"], ["file_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["audio_reference_id"], ["audio_references.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["narration_audio_asset_id"], ["file_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["output_video_asset_id"], ["file_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_task_id"], ["generation_tasks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_task_id"),
    )
    op.create_index(op.f("ix_video_tasks_audio_reference_id"), "video_tasks", ["audio_reference_id"], unique=False)
    op.create_index(op.f("ix_video_tasks_current_step"), "video_tasks", ["current_step"], unique=False)
    op.create_index(op.f("ix_video_tasks_owner_user_id"), "video_tasks", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_video_tasks_source_task_id"), "video_tasks", ["source_task_id"], unique=True)
    op.create_index(op.f("ix_video_tasks_status"), "video_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_video_tasks_status"), table_name="video_tasks")
    op.drop_index(op.f("ix_video_tasks_source_task_id"), table_name="video_tasks")
    op.drop_index(op.f("ix_video_tasks_owner_user_id"), table_name="video_tasks")
    op.drop_index(op.f("ix_video_tasks_current_step"), table_name="video_tasks")
    op.drop_index(op.f("ix_video_tasks_audio_reference_id"), table_name="video_tasks")
    op.drop_table("video_tasks")
    op.drop_index(op.f("ix_audio_references_owner_user_id"), table_name="audio_references")
    op.drop_index(op.f("ix_audio_references_deleted_at"), table_name="audio_references")
    op.drop_table("audio_references")
