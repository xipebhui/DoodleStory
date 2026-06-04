"""add content extraction story summary

Revision ID: f2b3c4d5e6a7
Revises: e1a2b3c4d5f6
Create Date: 2026-06-04 20:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2b3c4d5e6a7"
down_revision: Union[str, None] = "e1a2b3c4d5f6"
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
    columns = [
        ("story_content", sa.Column("story_content", sa.Text(), nullable=True)),
        ("story_highlight", sa.Column("story_highlight", sa.Text(), nullable=True)),
        ("target_audience", sa.Column("target_audience", sa.Text(), nullable=True)),
        ("story_summary_model", sa.Column("story_summary_model", sa.String(length=120), nullable=True)),
        ("story_summarized_at", sa.Column("story_summarized_at", sa.DateTime(), nullable=True)),
    ]
    for name, column in columns:
        if not has_column("content_extractions", name):
            op.add_column("content_extractions", column)


def downgrade() -> None:
    if not has_table("content_extractions"):
        return
    for name in [
        "story_summarized_at",
        "story_summary_model",
        "target_audience",
        "story_highlight",
        "story_content",
    ]:
        if has_column("content_extractions", name):
            op.drop_column("content_extractions", name)
