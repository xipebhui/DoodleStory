"""add youtube account style binding

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-07-30 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n5o6p7q8r9s0"
down_revision: Union[str, None] = "m4n5o6p7q8r9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("youtube_channels") as batch_op:
        batch_op.add_column(sa.Column("default_style_id", sa.String(32)))
        batch_op.add_column(sa.Column("style_bound_at", sa.DateTime()))
        batch_op.create_foreign_key(
            "fk_youtube_channels_default_style",
            "styles",
            ["default_style_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_youtube_channels_default_style_id",
            ["default_style_id"],
        )

    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.add_column(sa.Column("creation_channel_id", sa.String(32)))
        batch_op.create_foreign_key(
            "fk_native_agent_runs_creation_channel",
            "youtube_channels",
            ["creation_channel_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_native_agent_runs_creation_channel_id",
            ["creation_channel_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.drop_index("ix_native_agent_runs_creation_channel_id")
        batch_op.drop_constraint(
            "fk_native_agent_runs_creation_channel",
            type_="foreignkey",
        )
        batch_op.drop_column("creation_channel_id")

    with op.batch_alter_table("youtube_channels") as batch_op:
        batch_op.drop_index("ix_youtube_channels_default_style_id")
        batch_op.drop_constraint(
            "fk_youtube_channels_default_style",
            type_="foreignkey",
        )
        batch_op.drop_column("style_bound_at")
        batch_op.drop_column("default_style_id")
