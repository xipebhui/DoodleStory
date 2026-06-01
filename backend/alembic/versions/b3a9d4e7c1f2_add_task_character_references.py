"""add task character references

Revision ID: b3a9d4e7c1f2
Revises: 8f0b7c2a4d19
Create Date: 2026-06-01 18:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3a9d4e7c1f2"
down_revision: Union[str, None] = "8f0b7c2a4d19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

workflow_status = sa.Enum(
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancel_requested",
    "cancelled",
    "retrying",
    name="workflowstatus",
)


def table_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    task_columns = table_columns("generation_tasks")
    if "use_character_references" not in task_columns:
        with op.batch_alter_table("generation_tasks") as batch_op:
            batch_op.add_column(
                sa.Column("use_character_references", sa.Boolean(), nullable=False, server_default=sa.false())
            )

    op.create_table(
        "task_characters",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("task_id", sa.String(length=32), nullable=False),
        sa.Column("character_key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("importance", sa.String(length=40), nullable=False, server_default="primary"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["generation_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "character_key"),
    )
    op.create_index("ix_task_characters_task_id", "task_characters", ["task_id"], unique=False)

    op.create_table(
        "task_character_appearances",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("task_character_id", sa.String(length=32), nullable=False),
        sa.Column("appearance_key", sa.String(length=100), nullable=False),
        sa.Column("age_stage", sa.String(length=80), nullable=True),
        sa.Column("visual_prompt", sa.Text(), nullable=False),
        sa.Column("reference_prompt", sa.Text(), nullable=True),
        sa.Column("reference_image_id", sa.String(length=32), nullable=True),
        sa.Column("status", workflow_status, nullable=False, server_default="queued"),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["reference_image_id"], ["file_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_character_id"], ["task_characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_character_id", "appearance_key"),
    )
    op.create_index(
        "ix_task_character_appearances_task_character_id",
        "task_character_appearances",
        ["task_character_id"],
        unique=False,
    )
    op.create_index("ix_task_character_appearances_status", "task_character_appearances", ["status"], unique=False)

    op.create_table(
        "task_panel_character_appearances",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("panel_id", sa.String(length=32), nullable=False),
        sa.Column("task_character_appearance_id", sa.String(length=32), nullable=False),
        sa.Column("reference_order", sa.Integer(), nullable=False),
        sa.Column("usage_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint(
            "reference_order > 0",
            name="ck_task_panel_character_appearances_reference_order_positive",
        ),
        sa.ForeignKeyConstraint(["panel_id"], ["task_panels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_character_appearance_id"], ["task_character_appearances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("panel_id", "task_character_appearance_id"),
        sa.UniqueConstraint("panel_id", "reference_order"),
    )
    op.create_index(
        "ix_task_panel_character_appearances_panel_id",
        "task_panel_character_appearances",
        ["panel_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_panel_character_appearances_task_character_appearance_id",
        "task_panel_character_appearances",
        ["task_character_appearance_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_panel_character_appearances_task_character_appearance_id",
        table_name="task_panel_character_appearances",
    )
    op.drop_index("ix_task_panel_character_appearances_panel_id", table_name="task_panel_character_appearances")
    op.drop_table("task_panel_character_appearances")
    op.drop_index("ix_task_character_appearances_status", table_name="task_character_appearances")
    op.drop_index("ix_task_character_appearances_task_character_id", table_name="task_character_appearances")
    op.drop_table("task_character_appearances")
    op.drop_index("ix_task_characters_task_id", table_name="task_characters")
    op.drop_table("task_characters")

    if "use_character_references" in table_columns("generation_tasks"):
        with op.batch_alter_table("generation_tasks") as batch_op:
            batch_op.drop_column("use_character_references")
