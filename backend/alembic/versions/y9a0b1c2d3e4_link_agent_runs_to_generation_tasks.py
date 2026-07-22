"""link agent runs to generation tasks

Revision ID: y9a0b1c2d3e4
Revises: x8f9a0b1c2d3
Create Date: 2026-07-22 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "y9a0b1c2d3e4"
down_revision: Union[str, None] = "x8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.String(length=32), nullable=True))
        batch_op.create_foreign_key(
            "fk_agent_runs_task_id_generation_tasks",
            "generation_tasks",
            ["task_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_agent_runs_task_id", ["task_id"])


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_index("ix_agent_runs_task_id")
        batch_op.drop_constraint("fk_agent_runs_task_id_generation_tasks", type_="foreignkey")
        batch_op.drop_column("task_id")
