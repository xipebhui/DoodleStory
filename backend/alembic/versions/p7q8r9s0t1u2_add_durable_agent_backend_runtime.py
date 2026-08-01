"""add durable backend runtime without replacing native agent UI

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op


revision: str = "p7q8r9s0t1u2"
down_revision: str | None = "o6p7q8r9s0t1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RUNTIME_TABLES = (
    "agent_durable_workflows",
    "agent_durable_tasks",
    "agent_durable_attempts",
    "agent_durable_checkpoints",
    "agent_durable_artifacts",
    "agent_durable_gates",
    "agent_durable_tool_effects",
)


def upgrade() -> None:
    from app.core.database import Base
    from app.models import entities  # noqa: F401

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in RUNTIME_TABLES]
    Base.metadata.create_all(bind, tables=tables, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in reversed(RUNTIME_TABLES):
        op.drop_table(table_name)
