"""add native agent follow up run links

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "t1u2v3w4x5y6"
down_revision: str | None = "s0t1u2v3w4x5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.add_column(sa.Column("parent_run_id", sa.String(32)))
        batch_op.add_column(
            sa.Column("continued_from_checkpoint_id", sa.String(32))
        )
        batch_op.add_column(
            sa.Column("follow_up_idempotency_key", sa.String(160))
        )
        batch_op.add_column(
            sa.Column("follow_up_request_hash", sa.String(80))
        )
        batch_op.add_column(sa.Column("continuation_context_json", sa.Text()))
        batch_op.create_foreign_key(
            "fk_native_agent_runs_parent_run",
            "native_agent_runs",
            ["parent_run_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_native_agent_runs_follow_up_checkpoint",
            "agent_durable_checkpoints",
            ["continued_from_checkpoint_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_native_agent_runs_follow_up_idempotency",
            ["follow_up_idempotency_key"],
        )
        batch_op.create_check_constraint(
            "ck_native_agent_runs_follow_up_shape",
            "(parent_run_id IS NULL AND continued_from_checkpoint_id IS NULL "
            "AND follow_up_idempotency_key IS NULL "
            "AND follow_up_request_hash IS NULL "
            "AND continuation_context_json IS NULL) OR "
            "(parent_run_id IS NOT NULL "
            "AND continued_from_checkpoint_id IS NOT NULL "
            "AND follow_up_idempotency_key IS NOT NULL "
            "AND follow_up_request_hash IS NOT NULL "
            "AND continuation_context_json IS NOT NULL)",
        )
        batch_op.create_index(
            "ix_native_agent_runs_parent_run_id",
            ["parent_run_id"],
        )
        batch_op.create_index(
            "ix_native_agent_runs_follow_up_checkpoint_id",
            ["continued_from_checkpoint_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.drop_index("ix_native_agent_runs_follow_up_checkpoint_id")
        batch_op.drop_index("ix_native_agent_runs_parent_run_id")
        batch_op.drop_constraint(
            "ck_native_agent_runs_follow_up_shape",
            type_="check",
        )
        batch_op.drop_constraint(
            "uq_native_agent_runs_follow_up_idempotency",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_native_agent_runs_follow_up_checkpoint",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_native_agent_runs_parent_run",
            type_="foreignkey",
        )
        batch_op.drop_column("continuation_context_json")
        batch_op.drop_column("follow_up_request_hash")
        batch_op.drop_column("follow_up_idempotency_key")
        batch_op.drop_column("continued_from_checkpoint_id")
        batch_op.drop_column("parent_run_id")
