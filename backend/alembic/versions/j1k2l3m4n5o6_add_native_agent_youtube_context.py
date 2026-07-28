"""add native agent youtube publish context

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-07-28 23:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, None] = "i0j1k2l3m4n5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.add_column(sa.Column("youtube_channel_id", sa.String(32)))
        batch_op.add_column(sa.Column("youtube_publishable_video_id", sa.String(32)))
        batch_op.add_column(sa.Column("youtube_publish_confirmation_json", sa.Text()))
        batch_op.add_column(sa.Column("youtube_publish_confirmed_at", sa.DateTime()))
        batch_op.create_foreign_key(
            "fk_native_agent_runs_youtube_channel",
            "youtube_channels",
            ["youtube_channel_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_native_agent_runs_publishable_video",
            "publishable_videos",
            ["youtube_publishable_video_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_native_agent_runs_youtube_channel_id",
            ["youtube_channel_id"],
        )
        batch_op.create_index(
            "ix_native_agent_runs_youtube_publishable_video_id",
            ["youtube_publishable_video_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.drop_index("ix_native_agent_runs_youtube_publishable_video_id")
        batch_op.drop_index("ix_native_agent_runs_youtube_channel_id")
        batch_op.drop_constraint(
            "fk_native_agent_runs_publishable_video",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_native_agent_runs_youtube_channel",
            type_="foreignkey",
        )
        batch_op.drop_column("youtube_publish_confirmed_at")
        batch_op.drop_column("youtube_publish_confirmation_json")
        batch_op.drop_column("youtube_publishable_video_id")
        batch_op.drop_column("youtube_channel_id")
