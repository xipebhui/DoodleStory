"""add durable agent media runtime

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op


revision: str = "r9s0t1u2v3w4"
down_revision: str | None = "q8r9s0t1u2v3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.core.database import Base
    from app.models import entities  # noqa: F401

    for name in (
        "agent_durable_media_bindings",
        "agent_durable_image_qualities",
    ):
        Base.metadata.tables[name].create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    op.drop_table("agent_durable_image_qualities")
    op.drop_table("agent_durable_media_bindings")
