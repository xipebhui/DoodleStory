"""add native agent image provider snapshot

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-08-01 23:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p7q8r9s0t1u2"
down_revision: Union[str, None] = "o6p7q8r9s0t1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("native_agent_images") as batch_op:
        batch_op.add_column(
            sa.Column(
                "provider_snapshot",
                sa.String(length=80),
                nullable=False,
                server_default="qy",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("native_agent_images") as batch_op:
        batch_op.drop_column("provider_snapshot")
