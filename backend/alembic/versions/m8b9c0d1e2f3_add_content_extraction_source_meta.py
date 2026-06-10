"""add content extraction source meta

Revision ID: m8b9c0d1e2f3
Revises: l7a8b9c0d1e2
Create Date: 2026-06-10 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m8b9c0d1e2f3"
down_revision: Union[str, None] = "l7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = table_columns("content_extractions")
    with op.batch_alter_table("content_extractions") as batch_op:
        if "source_title" not in columns:
            batch_op.add_column(sa.Column("source_title", sa.Text(), nullable=True))
        if "source_description" not in columns:
            batch_op.add_column(sa.Column("source_description", sa.Text(), nullable=True))
        if "source_tags_json" not in columns:
            batch_op.add_column(sa.Column("source_tags_json", sa.Text(), nullable=True))


def downgrade() -> None:
    columns = table_columns("content_extractions")
    with op.batch_alter_table("content_extractions") as batch_op:
        if "source_tags_json" in columns:
            batch_op.drop_column("source_tags_json")
        if "source_description" in columns:
            batch_op.drop_column("source_description")
        if "source_title" in columns:
            batch_op.drop_column("source_title")
