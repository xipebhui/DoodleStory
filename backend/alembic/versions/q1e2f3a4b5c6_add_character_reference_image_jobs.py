"""add character reference image jobs

Revision ID: q1e2f3a4b5c6
Revises: p0d1e2f3a4b5
Create Date: 2026-06-19 00:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q1e2f3a4b5c6"
down_revision: Union[str, None] = "p0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("generated_images") as batch_op:
        batch_op.alter_column("panel_id", existing_type=sa.String(length=32), nullable=True)
        batch_op.add_column(
            sa.Column("job_kind", sa.String(length=40), nullable=False, server_default="panel_image")
        )
        batch_op.add_column(sa.Column("character_appearance_id", sa.String(length=32), nullable=True))
        batch_op.create_foreign_key(
            "fk_generated_images_character_appearance_id",
            "task_character_appearances",
            ["character_appearance_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_generated_images_job_kind", ["job_kind"], unique=False)
        batch_op.create_index("ix_generated_images_character_appearance_id", ["character_appearance_id"], unique=False)
        batch_op.create_check_constraint(
            "ck_generated_images_panel_job_panel",
            "job_kind != 'panel_image' OR panel_id IS NOT NULL",
        )
        batch_op.create_check_constraint(
            "ck_generated_images_character_job_appearance",
            "job_kind != 'character_reference' OR character_appearance_id IS NOT NULL",
        )


def downgrade() -> None:
    op.execute("DELETE FROM generated_images WHERE job_kind = 'character_reference'")
    with op.batch_alter_table("generated_images") as batch_op:
        batch_op.drop_constraint("ck_generated_images_character_job_appearance", type_="check")
        batch_op.drop_constraint("ck_generated_images_panel_job_panel", type_="check")
        batch_op.drop_index("ix_generated_images_character_appearance_id")
        batch_op.drop_index("ix_generated_images_job_kind")
        batch_op.drop_constraint("fk_generated_images_character_appearance_id", type_="foreignkey")
        batch_op.drop_column("character_appearance_id")
        batch_op.drop_column("job_kind")
        batch_op.alter_column("panel_id", existing_type=sa.String(length=32), nullable=False)
