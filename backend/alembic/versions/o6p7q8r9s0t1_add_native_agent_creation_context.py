"""add native agent creation account context snapshot

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-07-30 19:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o6p7q8r9s0t1"
down_revision: Union[str, None] = "n5o6p7q8r9s0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.add_column(
            sa.Column("creation_channel_context_json", sa.Text())
        )


def downgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.drop_column("creation_channel_context_json")
