"""add agent HITL artifacts approvals and event stream

Revision ID: z1a2b3c4d5e6
Revises: y9a0b1c2d3e4
Create Date: 2026-07-24 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z1a2b3c4d5e6"
down_revision: Union[str, None] = "y9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("artifact_type", sa.Enum("comic_plan", name="agentartifacttype"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "awaiting_approval",
                "approved",
                "rejected",
                "superseded",
                name="agentartifactstatus",
            ),
            nullable=False,
        ),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_agent_artifacts_version_positive"),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "artifact_type",
            "version",
            name="uq_agent_artifacts_run_type_version",
        ),
    )
    op.create_index(
        "ix_agent_artifacts_run_type_version",
        "agent_artifacts",
        ["run_id", "artifact_type", "version"],
    )
    op.create_index("ix_agent_artifacts_conversation_id", "agent_artifacts", ["conversation_id"])
    op.create_index("ix_agent_artifacts_run_id", "agent_artifacts", ["run_id"])

    op.create_table(
        "agent_approval_requests",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("artifact_id", sa.String(length=32), nullable=False),
        sa.Column("artifact_hash", sa.String(length=80), nullable=False),
        sa.Column("approval_type", sa.Enum("comic_plan", name="agentapprovaltype"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "changes_requested",
                "cancelled",
                name="agentapprovalstatus",
            ),
            nullable=False,
        ),
        sa.Column("requested_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by_user_id", sa.String(length=32), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["artifact_id"], ["agent_artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id"),
    )
    op.create_index(
        "ix_agent_approval_requests_conversation_id",
        "agent_approval_requests",
        ["conversation_id"],
    )
    op.create_index("ix_agent_approval_requests_run_id", "agent_approval_requests", ["run_id"])
    op.create_index("ix_agent_approval_requests_status", "agent_approval_requests", ["status"])

    op.create_table(
        "agent_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "run.started",
                "skill.loaded",
                "artifact.created",
                "approval.requested",
                "approval.resolved",
                "tool.started",
                "tool.progress",
                "tool.completed",
                "tool.failed",
                "assistant.message",
                "run.completed",
                "run.failed",
                name="agenteventtype",
            ),
            nullable=False,
        ),
        sa.Column("public_payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_agent_events_sequence_positive"),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_events_run_sequence"),
    )
    op.create_index(
        "ix_agent_events_conversation_created_sequence",
        "agent_events",
        ["conversation_id", "created_at", "sequence"],
    )
    op.create_index("ix_agent_events_conversation_id", "agent_events", ["conversation_id"])
    op.create_index("ix_agent_events_run_id", "agent_events", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_events_run_id", table_name="agent_events")
    op.drop_index("ix_agent_events_conversation_id", table_name="agent_events")
    op.drop_index("ix_agent_events_conversation_created_sequence", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index("ix_agent_approval_requests_status", table_name="agent_approval_requests")
    op.drop_index("ix_agent_approval_requests_run_id", table_name="agent_approval_requests")
    op.drop_index("ix_agent_approval_requests_conversation_id", table_name="agent_approval_requests")
    op.drop_table("agent_approval_requests")
    op.drop_index("ix_agent_artifacts_run_id", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_conversation_id", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_run_type_version", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
