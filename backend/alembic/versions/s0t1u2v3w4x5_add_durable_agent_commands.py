"""add durable agent commands

Revision ID: s0t1u2v3w4x5
Revises: r9s0t1u2v3w4
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op


revision: str = "s0t1u2v3w4x5"
down_revision: str | None = "r9s0t1u2v3w4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.core.database import Base
    from app.models import entities  # noqa: F401

    Base.metadata.tables["agent_durable_commands"].create(
        op.get_bind(),
        checkfirst=False,
    )


def downgrade() -> None:
    op.drop_table("agent_durable_commands")
