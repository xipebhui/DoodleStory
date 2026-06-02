"""add image text layout fields

Revision ID: d8c7e6f5a4b3
Revises: c4f0a8d2e9b1
Create Date: 2026-06-02 16:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8c7e6f5a4b3"
down_revision: Union[str, None] = "c4f0a8d2e9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    panel_columns = table_columns("task_panels")
    with op.batch_alter_table("task_panels") as batch_op:
        if "image_text_json" not in panel_columns:
            batch_op.add_column(sa.Column("image_text_json", sa.Text(), nullable=True))
        if "text_layout" not in panel_columns:
            batch_op.add_column(sa.Column("text_layout", sa.Text(), nullable=True))

    image_columns = table_columns("generated_images")
    with op.batch_alter_table("generated_images") as batch_op:
        if "image_text_json" not in image_columns:
            batch_op.add_column(sa.Column("image_text_json", sa.Text(), nullable=True))
        if "text_layout" not in image_columns:
            batch_op.add_column(sa.Column("text_layout", sa.Text(), nullable=True))


def downgrade() -> None:
    image_columns = table_columns("generated_images")
    with op.batch_alter_table("generated_images") as batch_op:
        if "text_layout" in image_columns:
            batch_op.drop_column("text_layout")
        if "image_text_json" in image_columns:
            batch_op.drop_column("image_text_json")

    panel_columns = table_columns("task_panels")
    with op.batch_alter_table("task_panels") as batch_op:
        if "text_layout" in panel_columns:
            batch_op.drop_column("text_layout")
        if "image_text_json" in panel_columns:
            batch_op.drop_column("image_text_json")
