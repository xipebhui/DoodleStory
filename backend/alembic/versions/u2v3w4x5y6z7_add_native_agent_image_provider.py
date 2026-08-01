"""add native agent image provider snapshot

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-08-01 23:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u2v3w4x5y6z7"
down_revision: Union[str, None] = "t1u2v3w4x5y6"
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
