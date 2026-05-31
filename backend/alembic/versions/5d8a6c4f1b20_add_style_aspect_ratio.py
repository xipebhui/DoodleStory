"""add style aspect ratio

Revision ID: 5d8a6c4f1b20
Revises: 2b6c1d7a9f30
Create Date: 2026-05-31 16:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5d8a6c4f1b20"
down_revision: Union[str, None] = "2b6c1d7a9f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_ASPECT_RATIO = "9:16"


def table_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def infer_existing_style_ratios() -> None:
    bind = op.get_bind()
    for ratio in ("16:9", "9:16", "4:3", "3:4", "1:1"):
        bind.execute(
            sa.text(
                "update styles set aspect_ratio = :ratio "
                "where style_prompt like :pattern and aspect_ratio = :default_ratio"
            ),
            {"ratio": ratio, "pattern": f"%{ratio}%", "default_ratio": DEFAULT_ASPECT_RATIO},
        )


def copy_style_ratio_to_table(table_name: str, style_column: str) -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"update {table_name} "
            f"set aspect_ratio_snapshot = coalesce((select styles.aspect_ratio from styles where styles.id = {table_name}.{style_column}), :default_ratio)"
        ),
        {"default_ratio": DEFAULT_ASPECT_RATIO},
    )


def copy_style_ratio_to_tasks() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "update generation_tasks "
            "set style_aspect_ratio_snapshot = coalesce((select styles.aspect_ratio from styles where styles.id = generation_tasks.style_id), :default_ratio)"
        ),
        {"default_ratio": DEFAULT_ASPECT_RATIO},
    )


def upgrade() -> None:
    if "aspect_ratio" not in table_columns("styles"):
        with op.batch_alter_table("styles") as batch_op:
            batch_op.add_column(sa.Column("aspect_ratio", sa.String(length=20), nullable=False, server_default=DEFAULT_ASPECT_RATIO))
        infer_existing_style_ratios()

    if "aspect_ratio_snapshot" not in table_columns("style_tests"):
        with op.batch_alter_table("style_tests") as batch_op:
            batch_op.add_column(
                sa.Column("aspect_ratio_snapshot", sa.String(length=20), nullable=False, server_default=DEFAULT_ASPECT_RATIO)
            )
        copy_style_ratio_to_table("style_tests", "style_id")

    if "style_aspect_ratio_snapshot" not in table_columns("generation_tasks"):
        with op.batch_alter_table("generation_tasks") as batch_op:
            batch_op.add_column(
                sa.Column("style_aspect_ratio_snapshot", sa.String(length=20), nullable=False, server_default=DEFAULT_ASPECT_RATIO)
            )
        copy_style_ratio_to_tasks()


def downgrade() -> None:
    if "style_aspect_ratio_snapshot" in table_columns("generation_tasks"):
        with op.batch_alter_table("generation_tasks") as batch_op:
            batch_op.drop_column("style_aspect_ratio_snapshot")
    if "aspect_ratio_snapshot" in table_columns("style_tests"):
        with op.batch_alter_table("style_tests") as batch_op:
            batch_op.drop_column("aspect_ratio_snapshot")
    if "aspect_ratio" in table_columns("styles"):
        with op.batch_alter_table("styles") as batch_op:
            batch_op.drop_column("aspect_ratio")
