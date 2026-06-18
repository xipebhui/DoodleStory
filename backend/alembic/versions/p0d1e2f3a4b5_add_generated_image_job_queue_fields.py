"""add generated image job queue fields

Revision ID: p0d1e2f3a4b5
Revises: n9c0d1e2f3a4
Create Date: 2026-06-18 23:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p0d1e2f3a4b5"
down_revision: Union[str, None] = "n9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not column_exists(table_name, column.name):
        op.add_column(table_name, column)


def create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    add_column_if_missing("generated_images", sa.Column("owner_user_id", sa.String(length=32), nullable=True))
    add_column_if_missing("generated_images", sa.Column("queued_at", sa.DateTime(), nullable=True))
    add_column_if_missing("generated_images", sa.Column("lease_until", sa.DateTime(), nullable=True))
    add_column_if_missing("generated_images", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    add_column_if_missing("generated_images", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    add_column_if_missing("generated_images", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
    add_column_if_missing("generated_images", sa.Column("queue_group", sa.String(length=120), nullable=True))
    add_column_if_missing("generated_images", sa.Column("locked_by", sa.String(length=120), nullable=True))

    create_index_if_missing("ix_generated_images_owner_user_id", "generated_images", ["owner_user_id"])
    create_index_if_missing("ix_generated_images_queued_at", "generated_images", ["queued_at"])
    create_index_if_missing("ix_generated_images_lease_until", "generated_images", ["lease_until"])
    create_index_if_missing("ix_generated_images_priority", "generated_images", ["priority"])
    create_index_if_missing("ix_generated_images_queue_group", "generated_images", ["queue_group"])
    create_index_if_missing("ix_generated_images_locked_by", "generated_images", ["locked_by"])

    op.execute(
        """
        UPDATE generated_images
        SET owner_user_id = (
            SELECT generation_tasks.owner_user_id
            FROM generation_tasks
            WHERE generation_tasks.id = generated_images.task_id
        )
        WHERE owner_user_id IS NULL
        """
    )
    op.execute("UPDATE generated_images SET queue_group = owner_user_id WHERE queue_group IS NULL")
    op.execute("UPDATE generated_images SET queued_at = created_at WHERE queued_at IS NULL")


def downgrade() -> None:
    if index_exists("generated_images", "ix_generated_images_locked_by"):
        op.drop_index("ix_generated_images_locked_by", table_name="generated_images")
    if index_exists("generated_images", "ix_generated_images_queue_group"):
        op.drop_index("ix_generated_images_queue_group", table_name="generated_images")
    if index_exists("generated_images", "ix_generated_images_priority"):
        op.drop_index("ix_generated_images_priority", table_name="generated_images")
    if index_exists("generated_images", "ix_generated_images_lease_until"):
        op.drop_index("ix_generated_images_lease_until", table_name="generated_images")
    if index_exists("generated_images", "ix_generated_images_queued_at"):
        op.drop_index("ix_generated_images_queued_at", table_name="generated_images")
    if index_exists("generated_images", "ix_generated_images_owner_user_id"):
        op.drop_index("ix_generated_images_owner_user_id", table_name="generated_images")

    for column_name in (
        "locked_by",
        "queue_group",
        "priority",
        "max_attempts",
        "attempts",
        "lease_until",
        "queued_at",
        "owner_user_id",
    ):
        if column_exists("generated_images", column_name):
            op.drop_column("generated_images", column_name)
