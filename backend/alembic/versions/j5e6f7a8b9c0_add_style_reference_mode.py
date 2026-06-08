"""add style reference mode

Revision ID: j5e6f7a8b9c0
Revises: h4d5e6f7a8b9
Create Date: 2026-06-08 19:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j5e6f7a8b9c0"
down_revision: Union[str, None] = "h4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_REFERENCE_MODE = "prompt"


def table_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def table_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def add_reference_mode_column(table_name: str, column_name: str) -> None:
    if column_name in table_columns(table_name):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(sa.Column(column_name, sa.String(length=20), nullable=False, server_default=DEFAULT_REFERENCE_MODE))


def upgrade() -> None:
    add_reference_mode_column("styles", "style_reference_mode")
    add_reference_mode_column("style_tests", "style_reference_mode_snapshot")
    add_reference_mode_column("generation_tasks", "style_reference_mode_snapshot")

    if "ix_styles_style_reference_mode" not in index_names("styles"):
        op.create_index("ix_styles_style_reference_mode", "styles", ["style_reference_mode"], unique=False)

    if "task_style_reference_images" not in table_names():
        op.create_table(
            "task_style_reference_images",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("task_id", sa.String(length=32), nullable=False),
            sa.Column("asset_id", sa.String(length=32), nullable=False),
            sa.Column("reference_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                "reference_order > 0",
                name="ck_task_style_reference_images_reference_order_positive",
            ),
            sa.ForeignKeyConstraint(["asset_id"], ["file_assets.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["task_id"], ["generation_tasks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id", "asset_id"),
            sa.UniqueConstraint("task_id", "reference_order"),
        )
    if "ix_task_style_reference_images_task_id" not in index_names("task_style_reference_images"):
        op.create_index(
            "ix_task_style_reference_images_task_id",
            "task_style_reference_images",
            ["task_id"],
            unique=False,
        )


def downgrade() -> None:
    if "ix_task_style_reference_images_task_id" in index_names("task_style_reference_images"):
        op.drop_index("ix_task_style_reference_images_task_id", table_name="task_style_reference_images")
    if "task_style_reference_images" in table_names():
        op.drop_table("task_style_reference_images")
    if "ix_styles_style_reference_mode" in index_names("styles"):
        op.drop_index("ix_styles_style_reference_mode", table_name="styles")
    if "style_reference_mode_snapshot" in table_columns("generation_tasks"):
        with op.batch_alter_table("generation_tasks") as batch_op:
            batch_op.drop_column("style_reference_mode_snapshot")
    if "style_reference_mode_snapshot" in table_columns("style_tests"):
        with op.batch_alter_table("style_tests") as batch_op:
            batch_op.drop_column("style_reference_mode_snapshot")
    if "style_reference_mode" in table_columns("styles"):
        with op.batch_alter_table("styles") as batch_op:
            batch_op.drop_column("style_reference_mode")
