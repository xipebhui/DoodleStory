"""add native agent subtitles and speech speed

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-07-28 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "native_agent_runs",
        sa.Column("subtitle_call_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "native_agent_audios",
        sa.Column("speed_snapshot", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "native_agent_audios",
        sa.Column("speech_rate_snapshot", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "native_agent_subtitles",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("audio_id", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("provider_snapshot", sa.String(length=80), nullable=False),
        sa.Column("model_snapshot", sa.String(length=160), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("cues_json", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["file_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["audio_id"], ["native_agent_audios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["native_agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
        sa.UniqueConstraint("audio_id"),
    )
    op.create_index("ix_native_agent_subtitles_run_id", "native_agent_subtitles", ["run_id"])
    op.create_index(
        "ix_native_agent_subtitles_run_created",
        "native_agent_subtitles",
        ["run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_native_agent_subtitles_run_created", table_name="native_agent_subtitles")
    op.drop_index("ix_native_agent_subtitles_run_id", table_name="native_agent_subtitles")
    op.drop_table("native_agent_subtitles")
    op.drop_column("native_agent_audios", "speech_rate_snapshot")
    op.drop_column("native_agent_audios", "speed_snapshot")
    op.drop_column("native_agent_runs", "subtitle_call_count")
