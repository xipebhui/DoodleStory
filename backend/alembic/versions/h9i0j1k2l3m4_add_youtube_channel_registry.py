"""add youtube channel and publishable video registry

Revision ID: h9i0j1k2l3m4
Revises: g8b9c0d1e2f3
Create Date: 2026-07-28 22:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h9i0j1k2l3m4"
down_revision: Union[str, None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "youtube_channels",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("channel_id", sa.String(80), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("handle", sa.String(255)),
        sa.Column("avatar_url", sa.String(1000)),
        sa.Column("account_email", sa.String(255)),
        sa.Column("remote_status", sa.String(40), nullable=False),
        sa.Column("alias", sa.String(120)),
        sa.Column("account_positioning", sa.Text()),
        sa.Column("target_audience", sa.Text()),
        sa.Column("stage_goal", sa.Text()),
        sa.Column("ai_definition", sa.Text()),
        sa.Column("operation_notes", sa.Text()),
        sa.Column("total_subscribers", sa.Integer()),
        sa.Column("total_views", sa.Integer()),
        sa.Column("total_watch_time_hours", sa.Float()),
        sa.Column("total_videos", sa.Integer()),
        sa.Column("analytics_json", sa.Text()),
        sa.Column("remote_last_sync_at", sa.DateTime()),
        sa.Column("last_sync_success_at", sa.DateTime()),
        sa.Column("last_sync_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.UniqueConstraint("channel_id"),
    )
    op.create_index("ix_youtube_channels_channel_id", "youtube_channels", ["channel_id"], unique=True)
    op.create_index("ix_youtube_channels_remote_status", "youtube_channels", ["remote_status"])
    op.create_index("ix_youtube_channels_alias", "youtube_channels", ["alias"])
    op.create_table(
        "youtube_channel_benchmarks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("channel_id", sa.String(32), nullable=False),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("platform_account_id", sa.String(160)),
        sa.Column("profile_url", sa.String(1000), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["youtube_channels.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("channel_id", "profile_url", name="uq_youtube_benchmark_channel_url"),
    )
    op.create_index("ix_youtube_channel_benchmarks_channel_id", "youtube_channel_benchmarks", ["channel_id"])
    op.create_table(
        "publishable_videos",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("source_native_agent_video_id", sa.String(32), nullable=False),
        sa.Column("video_url", sa.String(1000), nullable=False),
        sa.Column("thumbnail_url", sa.String(1000)),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("planned_publish_at", sa.DateTime()),
        sa.Column("contains_synthetic_media", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("review_status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_native_agent_video_id"], ["native_agent_videos.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("source_native_agent_video_id"),
    )
    op.create_index("ix_publishable_videos_owner_user_id", "publishable_videos", ["owner_user_id"])
    op.create_index("ix_publishable_videos_review_status", "publishable_videos", ["review_status"])
    op.create_table(
        "youtube_uploaded_videos",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("channel_id", sa.String(32), nullable=False),
        sa.Column("youtube_video_id", sa.String(80), nullable=False),
        sa.Column("remote_upload_task_id", sa.String(80)),
        sa.Column("title", sa.String(500)),
        sa.Column("description", sa.Text()),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("visibility", sa.String(40)),
        sa.Column("views", sa.Integer()),
        sa.Column("likes", sa.Integer()),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("remote_last_sync_at", sa.DateTime()),
        sa.Column("last_sync_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["youtube_channels.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("youtube_video_id"),
    )
    op.create_index("ix_youtube_uploaded_videos_channel_id", "youtube_uploaded_videos", ["channel_id"])
    op.create_index("ix_youtube_uploaded_videos_youtube_video_id", "youtube_uploaded_videos", ["youtube_video_id"], unique=True)
    op.create_index("ix_youtube_uploaded_channel_uploaded", "youtube_uploaded_videos", ["channel_id", "uploaded_at"])


def downgrade() -> None:
    op.drop_table("youtube_uploaded_videos")
    op.drop_table("publishable_videos")
    op.drop_table("youtube_channel_benchmarks")
    op.drop_table("youtube_channels")
