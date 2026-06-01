"""add story adaptation fields

Revision ID: c4f0a8d2e9b1
Revises: b3a9d4e7c1f2
Create Date: 2026-06-02 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f0a8d2e9b1"
down_revision: Union[str, None] = "b3a9d4e7c1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

story_input_mode = sa.Enum("original", "adapted", name="storyinputmode")
panel_type = sa.Enum("cover", "scene", name="paneltype")


def table_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    task_columns = table_columns("generation_tasks")
    with op.batch_alter_table("generation_tasks") as batch_op:
        if "story_input_mode" not in task_columns:
            batch_op.add_column(
                sa.Column("story_input_mode", story_input_mode, nullable=False, server_default="original")
            )
        if "adapted_story_title" not in task_columns:
            batch_op.add_column(sa.Column("adapted_story_title", sa.String(length=120), nullable=True))
        if "adapted_story_hook" not in task_columns:
            batch_op.add_column(sa.Column("adapted_story_hook", sa.Text(), nullable=True))
        if "adapted_story_text" not in task_columns:
            batch_op.add_column(sa.Column("adapted_story_text", sa.Text(), nullable=True))

    panel_columns = table_columns("task_panels")
    with op.batch_alter_table("task_panels") as batch_op:
        if "panel_type" not in panel_columns:
            batch_op.add_column(sa.Column("panel_type", panel_type, nullable=False, server_default="scene"))
        if "narration_text" not in panel_columns:
            batch_op.add_column(sa.Column("narration_text", sa.Text(), nullable=True))
        if "dialogue_text" not in panel_columns:
            batch_op.add_column(sa.Column("dialogue_text", sa.Text(), nullable=True))

    op.create_index("ix_generation_tasks_story_input_mode", "generation_tasks", ["story_input_mode"], unique=False)
    op.create_index("ix_task_panels_panel_type", "task_panels", ["panel_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_panels_panel_type", table_name="task_panels")
    op.drop_index("ix_generation_tasks_story_input_mode", table_name="generation_tasks")

    panel_columns = table_columns("task_panels")
    with op.batch_alter_table("task_panels") as batch_op:
        if "dialogue_text" in panel_columns:
            batch_op.drop_column("dialogue_text")
        if "narration_text" in panel_columns:
            batch_op.drop_column("narration_text")
        if "panel_type" in panel_columns:
            batch_op.drop_column("panel_type")

    task_columns = table_columns("generation_tasks")
    with op.batch_alter_table("generation_tasks") as batch_op:
        if "adapted_story_text" in task_columns:
            batch_op.drop_column("adapted_story_text")
        if "adapted_story_hook" in task_columns:
            batch_op.drop_column("adapted_story_hook")
        if "adapted_story_title" in task_columns:
            batch_op.drop_column("adapted_story_title")
        if "story_input_mode" in task_columns:
            batch_op.drop_column("story_input_mode")
