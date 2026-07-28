"""add native agent remotion video

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-28 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "native_agent_runs",
        sa.Column(
            "video_call_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_table(
        "native_agent_videos",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("bgm_asset_id", sa.String(length=32), nullable=True),
        sa.Column("template_id_snapshot", sa.String(length=120), nullable=False),
        sa.Column(
            "renderer_version_snapshot",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column("scenes_json", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("duration_in_frames", sa.Integer(), nullable=False),
        sa.Column("fps", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["file_assets.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["bgm_asset_id"],
            ["file_assets.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["native_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
    )
    op.create_index(
        "ix_native_agent_videos_run_id",
        "native_agent_videos",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_videos_run_created",
        "native_agent_videos",
        ["run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_agent_videos_run_created",
        table_name="native_agent_videos",
    )
    op.drop_index(
        "ix_native_agent_videos_run_id",
        table_name="native_agent_videos",
    )
    op.drop_table("native_agent_videos")
    op.drop_column("native_agent_runs", "video_call_count")
