"""add content extractions

Revision ID: e1a2b3c4d5f6
Revises: d8c7e6f5a4b3
Create Date: 2026-06-04 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, None] = "d8c7e6f5a4b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not has_table("content_extractions"):
        op.create_table(
            "content_extractions",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("owner_user_id", sa.String(length=32), nullable=False),
            sa.Column("raw_input", sa.Text(), nullable=False),
            sa.Column("source_url", sa.String(length=1000), nullable=False),
            sa.Column("media_type", sa.String(length=40), nullable=False),
            sa.Column("aweme_id", sa.String(length=80), nullable=True),
            sa.Column("output_dir", sa.String(length=1000), nullable=False),
            sa.Column("manifest_path", sa.String(length=1000), nullable=True),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_content_extractions_owner_user_id"), "content_extractions", ["owner_user_id"], unique=False)
        op.create_index(op.f("ix_content_extractions_source_url"), "content_extractions", ["source_url"], unique=False)
        op.create_index(op.f("ix_content_extractions_media_type"), "content_extractions", ["media_type"], unique=False)
        op.create_index(op.f("ix_content_extractions_aweme_id"), "content_extractions", ["aweme_id"], unique=False)

    if not has_table("content_extraction_media"):
        op.create_table(
            "content_extraction_media",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("content_extraction_id", sa.String(length=32), nullable=False),
            sa.Column("asset_id", sa.String(length=32), nullable=False),
            sa.Column("source_path", sa.String(length=1000), nullable=False),
            sa.Column(
                "media_kind",
                sa.Enum("image", "video", "audio", "metadata", name="contentextractionmediakind"),
                nullable=False,
            ),
            sa.Column("display_order", sa.Integer(), nullable=False),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("display_order > 0", name="ck_content_extraction_media_display_order_positive"),
            sa.ForeignKeyConstraint(["asset_id"], ["file_assets.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["content_extraction_id"], ["content_extractions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_content_extraction_media_content_extraction_id"),
            "content_extraction_media",
            ["content_extraction_id"],
            unique=False,
        )
        op.create_index(op.f("ix_content_extraction_media_asset_id"), "content_extraction_media", ["asset_id"], unique=False)
        op.create_index(op.f("ix_content_extraction_media_media_kind"), "content_extraction_media", ["media_kind"], unique=False)


def downgrade() -> None:
    if has_table("content_extraction_media"):
        op.drop_index(op.f("ix_content_extraction_media_media_kind"), table_name="content_extraction_media")
        op.drop_index(op.f("ix_content_extraction_media_asset_id"), table_name="content_extraction_media")
        op.drop_index(op.f("ix_content_extraction_media_content_extraction_id"), table_name="content_extraction_media")
        op.drop_table("content_extraction_media")

    if has_table("content_extractions"):
        op.drop_index(op.f("ix_content_extractions_aweme_id"), table_name="content_extractions")
        op.drop_index(op.f("ix_content_extractions_media_type"), table_name="content_extractions")
        op.drop_index(op.f("ix_content_extractions_source_url"), table_name="content_extractions")
        op.drop_index(op.f("ix_content_extractions_owner_user_id"), table_name="content_extractions")
        op.drop_table("content_extractions")
