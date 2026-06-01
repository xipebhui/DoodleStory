"""make generated images panel versions

Revision ID: 8f0b7c2a4d19
Revises: 5d8a6c4f1b20
Create Date: 2026-06-01 13:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f0b7c2a4d19"
down_revision: Union[str, None] = "5d8a6c4f1b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

generated_image_source_type = sa.Enum("initial", "user_edit", "retry", name="generatedimagesourcetype")
generated_image_workflow_step = sa.Enum("rewrite_prompt", "generate_image", name="generatedimageworkflowstep")


def table_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = table_columns("generated_images")
    naming_convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}

    with op.batch_alter_table("generated_images", naming_convention=naming_convention) as batch_op:
        if "generation_number" not in columns:
            batch_op.add_column(sa.Column("generation_number", sa.Integer(), nullable=False, server_default="1"))
        if "is_current" not in columns:
            batch_op.add_column(sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "source_type" not in columns:
            batch_op.add_column(
                sa.Column("source_type", generated_image_source_type, nullable=False, server_default="initial")
            )
        if "workflow_step" not in columns:
            batch_op.add_column(sa.Column("workflow_step", generated_image_workflow_step, nullable=True))
        if "user_instruction" not in columns:
            batch_op.add_column(sa.Column("user_instruction", sa.Text(), nullable=True))
        if "previous_prompt" not in columns:
            batch_op.add_column(sa.Column("previous_prompt", sa.Text(), nullable=True))
        if "image_prompt" not in columns:
            batch_op.add_column(sa.Column("image_prompt", sa.Text(), nullable=True))
        if "prompt_change_summary" not in columns:
            batch_op.add_column(sa.Column("prompt_change_summary", sa.Text(), nullable=True))
        if "llm_model_snapshot" not in columns:
            batch_op.add_column(sa.Column("llm_model_snapshot", sa.String(length=120), nullable=True))
        batch_op.alter_column("final_prompt", existing_type=sa.Text(), nullable=True)
        batch_op.drop_constraint("uq_generated_images_panel_id", type_="unique")
        batch_op.create_unique_constraint("uq_generated_images_panel_id_generation_number", ["panel_id", "generation_number"])
        batch_op.create_check_constraint("ck_generated_images_generation_number_positive", "generation_number > 0")

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "update generated_images "
            "set image_prompt = (select task_panels.generated_prompt from task_panels where task_panels.id = generated_images.panel_id) "
            "where image_prompt is null"
        )
    )
    bind.execute(sa.text("update generated_images set workflow_step = 'generate_image' where workflow_step is null"))
    bind.execute(sa.text("update generated_images set is_current = 1 where is_current is null"))

    op.create_index("ix_generated_images_panel_id", "generated_images", ["panel_id"], unique=False)
    op.create_index("ix_generated_images_is_current", "generated_images", ["is_current"], unique=False)
    op.create_index("ix_generated_images_source_type", "generated_images", ["source_type"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("generated_images") as batch_op:
        batch_op.drop_constraint("ck_generated_images_generation_number_positive", type_="check")
        batch_op.drop_constraint("uq_generated_images_panel_id_generation_number", type_="unique")
        batch_op.create_unique_constraint("uq_generated_images_panel_id", ["panel_id"])
        batch_op.alter_column("final_prompt", existing_type=sa.Text(), nullable=False)

    op.drop_index("ix_generated_images_source_type", table_name="generated_images")
    op.drop_index("ix_generated_images_is_current", table_name="generated_images")
    op.drop_index("ix_generated_images_panel_id", table_name="generated_images")

    columns = table_columns("generated_images")
    with op.batch_alter_table("generated_images") as batch_op:
        for column_name in (
            "llm_model_snapshot",
            "prompt_change_summary",
            "image_prompt",
            "previous_prompt",
            "user_instruction",
            "workflow_step",
            "source_type",
            "is_current",
            "generation_number",
        ):
            if column_name in columns:
                batch_op.drop_column(column_name)
