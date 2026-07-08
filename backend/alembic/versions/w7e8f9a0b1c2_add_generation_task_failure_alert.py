"""add generation task failure alert

Revision ID: w7e8f9a0b1c2
Revises: v6d7e8f9a0b1
Create Date: 2026-07-08 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w7e8f9a0b1c2"
down_revision: Union[str, None] = "v6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generation_tasks", sa.Column("failure_alert_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("generation_tasks", "failure_alert_sent_at")
