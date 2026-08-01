"""add durable agent plan revisions

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op


revision: str = "q8r9s0t1u2v3"
down_revision: str | None = "p7q8r9s0t1u2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.core.database import Base
    from app.models import entities  # noqa: F401

    table = Base.metadata.tables["agent_durable_plan_revisions"]
    table.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    op.drop_table("agent_durable_plan_revisions")
