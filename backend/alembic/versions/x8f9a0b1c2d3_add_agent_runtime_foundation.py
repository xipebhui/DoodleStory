"""add agent runtime foundation

Revision ID: x8f9a0b1c2d3
Revises: w7e8f9a0b1c2
Create Date: 2026-07-22 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x8f9a0b1c2d3"
down_revision: Union[str, None] = "w7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "archived", name="agentconversationstatus"),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_conversations_owner_user_id", "agent_conversations", ["owner_user_id"])
    op.create_index("ix_agent_conversations_status", "agent_conversations", ["status"])
    op.create_index("ix_agent_conversations_last_message_at", "agent_conversations", ["last_message_at"])
    op.create_index(
        "ix_agent_conversations_owner_last_message",
        "agent_conversations",
        ["owner_user_id", "last_message_at"],
    )

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("turn_id", sa.String(length=32), nullable=True),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", "system_event", "task_card", name="agentmessagerole"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("resource_refs_json", sa.Text(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_agent_messages_sequence_positive"),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "sequence", name="uq_agent_messages_conversation_sequence"),
    )
    op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])
    op.create_index("ix_agent_messages_turn_id", "agent_messages", ["turn_id"])
    op.create_index("ix_agent_messages_role", "agent_messages", ["role"])
    op.create_index(
        "ix_agent_messages_conversation_sequence",
        "agent_messages",
        ["conversation_id", "sequence"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("turn_id", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "waiting_for_tool",
                "waiting_for_input",
                "paused",
                "retrying",
                "succeeded",
                "failed",
                "cancel_requested",
                "cancelled",
                name="agentrunstatus",
            ),
            nullable=False,
        ),
        sa.Column("current_step_sequence", sa.Integer(), nullable=False),
        sa.Column("model_call_count", sa.Integer(), nullable=False),
        sa.Column("image_call_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("internal_error_ref", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "turn_id", name="uq_agent_runs_conversation_turn"),
    )
    op.create_index("ix_agent_runs_conversation_id", "agent_runs", ["conversation_id"])
    op.create_index("ix_agent_runs_turn_id", "agent_runs", ["turn_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_status_updated", "agent_runs", ["status", "updated_at"])
    op.create_index("ix_agent_runs_conversation_created", "agent_runs", ["conversation_id", "created_at"])

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "step_type",
            sa.Enum("model_call", "tool_call", "tool_result", "wait", "final", name="agentsteptype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "succeeded", "failed", "cancelled", name="agentstepstatus"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=160), nullable=True),
        sa.Column("api_shape", sa.String(length=80), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("fallback_from", sa.String(length=80), nullable=True),
        sa.Column("fallback_reason", sa.String(length=120), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("usage_json", sa.Text(), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("input_ref", sa.Text(), nullable=True),
        sa.Column("output_ref", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("internal_error_ref", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("attempt > 0", name="ck_agent_steps_attempt_positive"),
        sa.CheckConstraint("sequence > 0", name="ck_agent_steps_sequence_positive"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_agent_steps_idempotency_key"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_steps_run_sequence"),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])
    op.create_index("ix_agent_steps_step_type", "agent_steps", ["step_type"])
    op.create_index("ix_agent_steps_status", "agent_steps", ["status"])
    op.create_index("ix_agent_steps_run_sequence", "agent_steps", ["run_id", "sequence"])


def downgrade() -> None:
    op.drop_table("agent_steps")
    op.drop_table("agent_runs")
    op.drop_table("agent_messages")
    op.drop_table("agent_conversations")
