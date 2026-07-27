"""add native agent speech audio

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-28 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "native_agent_runs",
        sa.Column(
            "speech_call_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_table(
        "native_agent_audios",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("provider_snapshot", sa.String(length=80), nullable=False),
        sa.Column("resource_id_snapshot", sa.String(length=120), nullable=False),
        sa.Column("model_snapshot", sa.String(length=160), nullable=False),
        sa.Column("speaker_snapshot", sa.String(length=255), nullable=False),
        sa.Column("response_format_snapshot", sa.String(length=20), nullable=False),
        sa.Column("sample_rate_snapshot", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
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
            ["run_id"],
            ["native_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
    )
    op.create_index(
        "ix_native_agent_audios_run_id",
        "native_agent_audios",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_audios_run_created",
        "native_agent_audios",
        ["run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_agent_audios_run_created",
        table_name="native_agent_audios",
    )
    op.drop_index(
        "ix_native_agent_audios_run_id",
        table_name="native_agent_audios",
    )
    op.drop_table("native_agent_audios")
    op.drop_column("native_agent_runs", "speech_call_count")
