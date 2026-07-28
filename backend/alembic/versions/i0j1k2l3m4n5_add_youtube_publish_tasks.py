"""add youtube publish tasks and permanent source links

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-07-28 23:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i0j1k2l3m4n5"
down_revision: Union[str, None] = "h9i0j1k2l3m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "youtube_publish_tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("channel_id", sa.String(32), nullable=False),
        sa.Column("publishable_video_id", sa.String(32), nullable=False),
        sa.Column("source_native_agent_video_id", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("remote_task_id", sa.String(80)),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("remote_status", sa.String(40)),
        sa.Column("title_snapshot", sa.String(200), nullable=False),
        sa.Column("description_snapshot", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("thumbnail_url_snapshot", sa.String(1000)),
        sa.Column("video_url_snapshot", sa.String(1000), nullable=False),
        sa.Column("visibility_snapshot", sa.String(40), nullable=False),
        sa.Column("contains_synthetic_media_snapshot", sa.Boolean(), nullable=False),
        sa.Column("planned_publish_at", sa.DateTime(), nullable=False),
        sa.Column("notify_subscribers", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("last_status_checked_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("youtube_video_id", sa.String(80)),
        sa.Column("youtube_url", sa.String(1000)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.Column("remote_payload_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["youtube_channels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["publishable_video_id"], ["publishable_videos.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_native_agent_video_id"], ["native_agent_videos.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("remote_task_id"),
        sa.UniqueConstraint("youtube_video_id"),
        sa.UniqueConstraint(
            "channel_id",
            "publishable_video_id",
            name="uq_youtube_publish_task_channel_video",
        ),
    )
    op.create_index("ix_youtube_publish_tasks_owner_user_id", "youtube_publish_tasks", ["owner_user_id"])
    op.create_index("ix_youtube_publish_tasks_channel_id", "youtube_publish_tasks", ["channel_id"])
    op.create_index("ix_youtube_publish_tasks_publishable_video_id", "youtube_publish_tasks", ["publishable_video_id"])
    op.create_index("ix_youtube_publish_tasks_source_native_agent_video_id", "youtube_publish_tasks", ["source_native_agent_video_id"])
    op.create_index("ix_youtube_publish_tasks_status", "youtube_publish_tasks", ["status"])

    with op.batch_alter_table("youtube_uploaded_videos") as batch_op:
        batch_op.add_column(sa.Column("publish_task_id", sa.String(32)))
        batch_op.add_column(sa.Column("source_native_agent_video_id", sa.String(32)))
        batch_op.create_foreign_key(
            "fk_youtube_uploaded_videos_publish_task",
            "youtube_publish_tasks",
            ["publish_task_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_youtube_uploaded_videos_native_video",
            "native_agent_videos",
            ["source_native_agent_video_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_youtube_uploaded_videos_publish_task",
            ["publish_task_id"],
        )
        batch_op.create_index(
            "ix_youtube_uploaded_videos_source_native_agent_video_id",
            ["source_native_agent_video_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("youtube_uploaded_videos") as batch_op:
        batch_op.drop_index("ix_youtube_uploaded_videos_source_native_agent_video_id")
        batch_op.drop_constraint("uq_youtube_uploaded_videos_publish_task", type_="unique")
        batch_op.drop_constraint("fk_youtube_uploaded_videos_native_video", type_="foreignkey")
        batch_op.drop_constraint("fk_youtube_uploaded_videos_publish_task", type_="foreignkey")
        batch_op.drop_column("source_native_agent_video_id")
        batch_op.drop_column("publish_task_id")
    op.drop_table("youtube_publish_tasks")
