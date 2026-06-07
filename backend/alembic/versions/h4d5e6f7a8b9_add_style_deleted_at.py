"""add style deleted at

Revision ID: h4d5e6f7a8b9
Revises: g3c4d5e6f7a8
Create Date: 2026-06-07 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h4d5e6f7a8b9"
down_revision: Union[str, None] = "g3c4d5e6f7a8"
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
    if "deleted_at" not in table_columns("styles"):
        with op.batch_alter_table("styles") as batch_op:
            batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
    if "ix_styles_deleted_at" not in index_names("styles"):
        op.create_index("ix_styles_deleted_at", "styles", ["deleted_at"], unique=False)


def downgrade() -> None:
    if "ix_styles_deleted_at" in index_names("styles"):
        op.drop_index("ix_styles_deleted_at", table_name="styles")
    if "deleted_at" in table_columns("styles"):
        with op.batch_alter_table("styles") as batch_op:
            batch_op.drop_column("deleted_at")
