"""add video task render fields

Revision ID: t4b5c6d7e8f9
Revises: s3a4b5c6d7e8
Create Date: 2026-06-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t4b5c6d7e8f9"
down_revision: Union[str, None] = "s3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("video_tasks", sa.Column("voice_provider_snapshot", sa.String(length=80), nullable=True))
    op.add_column("video_tasks", sa.Column("voice_model_snapshot", sa.String(length=160), nullable=True))
    op.add_column("video_tasks", sa.Column("voice_name_snapshot", sa.String(length=255), nullable=True))
    op.add_column("video_tasks", sa.Column("video_provider_job_id", sa.String(length=120), nullable=True))
    op.add_column("video_tasks", sa.Column("video_provider_status", sa.String(length=80), nullable=True))
    op.add_column("video_tasks", sa.Column("video_provider_output_url", sa.String(length=1000), nullable=True))
    op.add_column("video_tasks", sa.Column("video_episode_json", sa.Text(), nullable=True))
    op.add_column("video_tasks", sa.Column("video_provider_result_json", sa.Text(), nullable=True))

    op.create_table(
        "video_task_audio_segments",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("video_task_id", sa.String(length=32), nullable=False),
        sa.Column("panel_id", sa.String(length=32), nullable=False),
        sa.Column("panel_order", sa.Integer(), nullable=False),
        sa.Column("narration_text", sa.Text(), nullable=False),
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("panel_order > 0", name="ck_video_task_audio_segments_panel_order_positive"),
        sa.ForeignKeyConstraint(["asset_id"], ["file_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["panel_id"], ["task_panels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_task_id"], ["video_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_task_id", "panel_id"),
    )
    op.create_index(
        op.f("ix_video_task_audio_segments_panel_id"),
        "video_task_audio_segments",
        ["panel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_video_task_audio_segments_video_task_id"),
        "video_task_audio_segments",
        ["video_task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_video_task_audio_segments_video_task_id"), table_name="video_task_audio_segments")
    op.drop_index(op.f("ix_video_task_audio_segments_panel_id"), table_name="video_task_audio_segments")
    op.drop_table("video_task_audio_segments")
    op.drop_column("video_tasks", "video_provider_result_json")
    op.drop_column("video_tasks", "video_episode_json")
    op.drop_column("video_tasks", "video_provider_output_url")
    op.drop_column("video_tasks", "video_provider_status")
    op.drop_column("video_tasks", "video_provider_job_id")
    op.drop_column("video_tasks", "voice_name_snapshot")
    op.drop_column("video_tasks", "voice_model_snapshot")
    op.drop_column("video_tasks", "voice_provider_snapshot")
