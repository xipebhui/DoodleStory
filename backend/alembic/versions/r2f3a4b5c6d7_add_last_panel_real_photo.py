"""add last panel real photo flag

Revision ID: r2f3a4b5c6d7
Revises: q1e2f3a4b5c6
Create Date: 2026-06-24 20:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r2f3a4b5c6d7"
down_revision: Union[str, None] = "q1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "generation_tasks",
        sa.Column("last_panel_real_photo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("generation_tasks", "last_panel_real_photo")
