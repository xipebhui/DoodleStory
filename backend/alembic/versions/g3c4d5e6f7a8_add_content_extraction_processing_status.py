"""add content extraction processing status

Revision ID: g3c4d5e6f7a8
Revises: f2b3c4d5e6a7
Create Date: 2026-06-04 22:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g3c4d5e6f7a8"
down_revision: Union[str, None] = "f2b3c4d5e6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not has_table("content_extractions"):
        return
    if not has_column("content_extractions", "processing_status"):
        op.add_column(
            "content_extractions",
            sa.Column("processing_status", sa.String(length=40), server_default="succeeded", nullable=False),
        )
        op.create_index(
            op.f("ix_content_extractions_processing_status"),
            "content_extractions",
            ["processing_status"],
            unique=False,
        )
    if not has_column("content_extractions", "processing_error_message"):
        op.add_column("content_extractions", sa.Column("processing_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    if not has_table("content_extractions"):
        return
    if has_column("content_extractions", "processing_error_message"):
        op.drop_column("content_extractions", "processing_error_message")
    if has_column("content_extractions", "processing_status"):
        op.drop_index(op.f("ix_content_extractions_processing_status"), table_name="content_extractions")
        op.drop_column("content_extractions", "processing_status")
