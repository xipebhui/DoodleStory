"""replace generation profile with image model

Revision ID: 2b6c1d7a9f30
Revises: ae07b5f5d15f
Create Date: 2026-05-30 23:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b6c1d7a9f30"
down_revision: Union[str, None] = "ae07b5f5d15f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_IMAGE_MODEL_NAME = "gpt-image-2"


def table_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    style_columns = table_columns("styles")
    style_indexes = index_names("styles")
    if "generation_profile_key" in style_columns and "ix_styles_generation_profile_key" in style_indexes:
        op.drop_index("ix_styles_generation_profile_key", table_name="styles")
    if "image_model_name" not in style_columns:
        with op.batch_alter_table("styles") as batch_op:
            batch_op.add_column(
                sa.Column("image_model_name", sa.String(length=120), nullable=False, server_default=DEFAULT_IMAGE_MODEL_NAME)
            )
    if "generation_profile_key" in style_columns:
        with op.batch_alter_table("styles") as batch_op:
            batch_op.drop_column("generation_profile_key")
    if "ix_styles_image_model_name" not in index_names("styles"):
        op.create_index("ix_styles_image_model_name", "styles", ["image_model_name"], unique=False)

    for table_name in ("style_tests", "generation_tasks", "generated_images"):
        columns = table_columns(table_name)
        if "image_model_name_snapshot" not in columns:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "image_model_name_snapshot",
                        sa.String(length=120),
                        nullable=False,
                        server_default=DEFAULT_IMAGE_MODEL_NAME,
                    )
                )
        if "generation_profile_key_snapshot" in columns:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column("generation_profile_key_snapshot")


def downgrade() -> None:
    if "ix_styles_image_model_name" in index_names("styles"):
        op.drop_index("ix_styles_image_model_name", table_name="styles")
    if "generation_profile_key" not in table_columns("styles"):
        with op.batch_alter_table("styles") as batch_op:
            batch_op.add_column(sa.Column("generation_profile_key", sa.String(length=120), nullable=True))
    if "image_model_name" in table_columns("styles"):
        with op.batch_alter_table("styles") as batch_op:
            batch_op.drop_column("image_model_name")
    if "ix_styles_generation_profile_key" not in index_names("styles"):
        op.create_index("ix_styles_generation_profile_key", "styles", ["generation_profile_key"], unique=False)

    for table_name in ("style_tests", "generation_tasks", "generated_images"):
        columns = table_columns(table_name)
        if "generation_profile_key_snapshot" not in columns:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column("generation_profile_key_snapshot", sa.String(length=120), nullable=True))
        if "image_model_name_snapshot" in columns:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column("image_model_name_snapshot")
