"""add native agent external contents

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-07-29 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, None] = "j1k2l3m4n5o6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "native_agent_external_contents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(32),
            sa.ForeignKey("native_agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "content_asset_id",
            sa.String(32),
            sa.ForeignKey("file_assets.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("content_type", sa.String(80)),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("resolved_url", sa.String(1000), nullable=False),
        sa.Column("source_content_id", sa.String(255)),
        sa.Column("title", sa.String(500)),
        sa.Column("description", sa.Text()),
        sa.Column("author_name", sa.String(255)),
        sa.Column("publish_time", sa.String(255)),
        sa.Column("publish_timestamp", sa.Integer()),
        sa.Column("tags_json", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_native_agent_external_contents_run_id",
        "native_agent_external_contents",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_external_contents_platform",
        "native_agent_external_contents",
        ["platform"],
    )
    op.create_index(
        "ix_native_agent_external_contents_run_created",
        "native_agent_external_contents",
        ["run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("native_agent_external_contents")
