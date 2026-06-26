"""add generation task remove image text

Revision ID: v6d7e8f9a0b1
Revises: u5c6d7e8f9a0
Create Date: 2026-06-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v6d7e8f9a0b1"
down_revision: Union[str, None] = "u5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "generation_tasks",
        sa.Column("remove_image_text", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("generation_tasks", "remove_image_text")
