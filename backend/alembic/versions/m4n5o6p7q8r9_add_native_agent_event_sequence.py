"""add native agent event sequence counter

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-07-29 01:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, None] = "l3m4n5o6p7q8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "event_sequence",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    op.execute(
        """
        UPDATE native_agent_runs
        SET event_sequence = COALESCE(
            (
                SELECT MAX(native_agent_events.sequence)
                FROM native_agent_events
                WHERE native_agent_events.run_id = native_agent_runs.id
            ),
            0
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.drop_column("event_sequence")
