"""add minimal native agent loop

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-07-26 20:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


agent_run_status = sa.Enum(
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
    create_type=False,
)
native_item_type = sa.Enum(
    "user_input",
    "tool_call",
    "tool_result",
    "assistant_output",
    "error",
    name="nativeagentitemtype",
)


def upgrade() -> None:
    op.create_table(
        "native_agent_conversations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column(
            "last_message_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_native_agent_conversations_owner_user_id",
        "native_agent_conversations",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_native_agent_conversations_last_message_at",
        "native_agent_conversations",
        ["last_message_at"],
    )
    op.create_index(
        "ix_native_agent_conversations_owner_last_message",
        "native_agent_conversations",
        ["owner_user_id", "last_message_at"],
    )

    op.create_table(
        "native_agent_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("skill_version_id", sa.String(length=32), nullable=False),
        sa.Column("style_id", sa.String(length=32), nullable=True),
        sa.Column("status", agent_run_status, nullable=False),
        sa.Column("model_snapshot", sa.String(length=160), nullable=False),
        sa.Column("skill_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("skill_version_snapshot", sa.Integer(), nullable=False),
        sa.Column("skill_content_hash_snapshot", sa.String(length=80), nullable=False),
        sa.Column("style_name_snapshot", sa.String(length=80), nullable=True),
        sa.Column("style_prompt_snapshot", sa.Text(), nullable=True),
        sa.Column("image_model_snapshot", sa.String(length=120), nullable=True),
        sa.Column("aspect_ratio_snapshot", sa.String(length=20), nullable=True),
        sa.Column("style_reference_urls_json", sa.Text(), nullable=True),
        sa.Column("model_call_count", sa.Integer(), nullable=False),
        sa.Column("image_call_count", sa.Integer(), nullable=False),
        sa.Column("final_output", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["native_agent_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_version_id"],
            ["agent_skill_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["style_id"], ["styles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_native_agent_runs_conversation_id",
        "native_agent_runs",
        ["conversation_id"],
    )
    op.create_index(
        "ix_native_agent_runs_skill_version_id",
        "native_agent_runs",
        ["skill_version_id"],
    )
    op.create_index(
        "ix_native_agent_runs_style_id",
        "native_agent_runs",
        ["style_id"],
    )
    op.create_index(
        "ix_native_agent_runs_status",
        "native_agent_runs",
        ["status"],
    )
    op.create_index(
        "ix_native_agent_runs_conversation_created",
        "native_agent_runs",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "native_agent_items",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("item_type", native_item_type, nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sequence > 0",
            name="ck_native_agent_items_sequence_positive",
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
            name="uq_native_agent_items_run_sequence",
        ),
    )
    op.create_index(
        "ix_native_agent_items_run_id",
        "native_agent_items",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_items_item_type",
        "native_agent_items",
        ["item_type"],
    )
    op.create_index(
        "ix_native_agent_items_run_sequence",
        "native_agent_items",
        ["run_id", "sequence"],
    )

    op.create_table(
        "native_agent_images",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("image_model_snapshot", sa.String(length=120), nullable=False),
        sa.Column("aspect_ratio_snapshot", sa.String(length=20), nullable=False),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(["asset_id"], ["file_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["native_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
    )
    op.create_index(
        "ix_native_agent_images_run_id",
        "native_agent_images",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_images_run_created",
        "native_agent_images",
        ["run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_native_agent_images_run_created", table_name="native_agent_images")
    op.drop_index("ix_native_agent_images_run_id", table_name="native_agent_images")
    op.drop_table("native_agent_images")
    op.drop_index("ix_native_agent_items_run_sequence", table_name="native_agent_items")
    op.drop_index("ix_native_agent_items_item_type", table_name="native_agent_items")
    op.drop_index("ix_native_agent_items_run_id", table_name="native_agent_items")
    op.drop_table("native_agent_items")
    op.drop_index("ix_native_agent_runs_conversation_created", table_name="native_agent_runs")
    op.drop_index("ix_native_agent_runs_status", table_name="native_agent_runs")
    op.drop_index("ix_native_agent_runs_style_id", table_name="native_agent_runs")
    op.drop_index("ix_native_agent_runs_skill_version_id", table_name="native_agent_runs")
    op.drop_index("ix_native_agent_runs_conversation_id", table_name="native_agent_runs")
    op.drop_table("native_agent_runs")
    op.drop_index(
        "ix_native_agent_conversations_owner_last_message",
        table_name="native_agent_conversations",
    )
    op.drop_index(
        "ix_native_agent_conversations_last_message_at",
        table_name="native_agent_conversations",
    )
    op.drop_index(
        "ix_native_agent_conversations_owner_user_id",
        table_name="native_agent_conversations",
    )
    op.drop_table("native_agent_conversations")
    native_item_type.drop(op.get_bind(), checkfirst=True)
