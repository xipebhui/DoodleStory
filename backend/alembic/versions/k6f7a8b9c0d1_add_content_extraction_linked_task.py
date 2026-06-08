"""add content extraction linked task

Revision ID: k6f7a8b9c0d1
Revises: j5e6f7a8b9c0
Create Date: 2026-06-08 20:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k6f7a8b9c0d1"
down_revision: Union[str, None] = "j5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def upgrade() -> None:
    columns = table_columns("content_extractions")
    with op.batch_alter_table("content_extractions") as batch_op:
        if "linked_task_id" not in columns:
            batch_op.add_column(sa.Column("linked_task_id", sa.String(length=32), nullable=True))
            batch_op.create_foreign_key(
                "fk_content_extractions_linked_task_id_generation_tasks",
                "generation_tasks",
                ["linked_task_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "task_create_status" not in columns:
            batch_op.add_column(sa.Column("task_create_status", sa.String(length=40), nullable=True))
        if "task_create_error_message" not in columns:
            batch_op.add_column(sa.Column("task_create_error_message", sa.Text(), nullable=True))

    indexes = index_names("content_extractions")
    if "ix_content_extractions_linked_task_id" not in indexes:
        op.create_index(
            "ix_content_extractions_linked_task_id",
            "content_extractions",
            ["linked_task_id"],
            unique=False,
        )
    if "ix_content_extractions_task_create_status" not in indexes:
        op.create_index(
            "ix_content_extractions_task_create_status",
            "content_extractions",
            ["task_create_status"],
            unique=False,
        )


def downgrade() -> None:
    indexes = index_names("content_extractions")
    if "ix_content_extractions_task_create_status" in indexes:
        op.drop_index("ix_content_extractions_task_create_status", table_name="content_extractions")
    if "ix_content_extractions_linked_task_id" in indexes:
        op.drop_index("ix_content_extractions_linked_task_id", table_name="content_extractions")

    columns = table_columns("content_extractions")
    with op.batch_alter_table("content_extractions") as batch_op:
        if "task_create_error_message" in columns:
            batch_op.drop_column("task_create_error_message")
        if "task_create_status" in columns:
            batch_op.drop_column("task_create_status")
        if "linked_task_id" in columns:
            batch_op.drop_column("linked_task_id")
