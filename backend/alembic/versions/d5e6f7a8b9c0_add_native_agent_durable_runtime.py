"""add native agent durable runtime

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-27 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


native_step_type = sa.Enum(
    "model_call",
    "tool_call",
    "final",
    name="nativeagentsteptype",
)
native_step_status = sa.Enum(
    "prepared",
    "running",
    "succeeded",
    "failed",
    "unknown",
    name="nativeagentstepstatus",
)


def upgrade() -> None:
    op.create_table(
        "native_agent_steps",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("step_type", native_step_type, nullable=False),
        sa.Column("status", native_step_status, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("input_summary_json", sa.Text(), nullable=True),
        sa.Column("output_ref_json", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_native_agent_steps_attempts_non_negative",
        ),
        sa.CheckConstraint(
            "sequence > 0",
            name="ck_native_agent_steps_sequence_positive",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["native_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_native_agent_steps_idempotency_key",
        ),
        sa.UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_native_agent_steps_run_sequence",
        ),
    )
    op.create_index(
        "ix_native_agent_steps_run_id",
        "native_agent_steps",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_steps_step_type",
        "native_agent_steps",
        ["step_type"],
    )
    op.create_index(
        "ix_native_agent_steps_status",
        "native_agent_steps",
        ["status"],
    )
    op.create_index(
        "ix_native_agent_steps_tool_call_id",
        "native_agent_steps",
        ["tool_call_id"],
    )
    op.create_index(
        "ix_native_agent_steps_run_sequence",
        "native_agent_steps",
        ["run_id", "sequence"],
    )

    op.create_table(
        "native_agent_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sequence > 0",
            name="ck_native_agent_events_sequence_positive",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["native_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_native_agent_events_run_sequence",
        ),
    )
    op.create_index(
        "ix_native_agent_events_run_id",
        "native_agent_events",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_events_event_type",
        "native_agent_events",
        ["event_type"],
    )
    op.create_index(
        "ix_native_agent_events_run_sequence",
        "native_agent_events",
        ["run_id", "sequence"],
    )

    op.create_table(
        "native_agent_context_items",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("item_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sequence > 0",
            name="ck_native_agent_context_items_sequence_positive",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["native_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_native_agent_context_items_run_sequence",
        ),
    )
    op.create_index(
        "ix_native_agent_context_items_run_id",
        "native_agent_context_items",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_context_items_run_sequence",
        "native_agent_context_items",
        ["run_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_agent_context_items_run_sequence",
        table_name="native_agent_context_items",
    )
    op.drop_index(
        "ix_native_agent_context_items_run_id",
        table_name="native_agent_context_items",
    )
    op.drop_table("native_agent_context_items")

    op.drop_index(
        "ix_native_agent_events_run_sequence",
        table_name="native_agent_events",
    )
    op.drop_index(
        "ix_native_agent_events_event_type",
        table_name="native_agent_events",
    )
    op.drop_index(
        "ix_native_agent_events_run_id",
        table_name="native_agent_events",
    )
    op.drop_table("native_agent_events")

    op.drop_index(
        "ix_native_agent_steps_run_sequence",
        table_name="native_agent_steps",
    )
    op.drop_index(
        "ix_native_agent_steps_tool_call_id",
        table_name="native_agent_steps",
    )
    op.drop_index(
        "ix_native_agent_steps_status",
        table_name="native_agent_steps",
    )
    op.drop_index(
        "ix_native_agent_steps_step_type",
        table_name="native_agent_steps",
    )
    op.drop_index(
        "ix_native_agent_steps_run_id",
        table_name="native_agent_steps",
    )
    op.drop_table("native_agent_steps")
