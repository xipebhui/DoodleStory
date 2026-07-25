"""add generated image acceptance facts

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-07-24 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("generated_images") as batch_op:
        batch_op.add_column(sa.Column("accepted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("accepted_by_user_id", sa.String(length=32), nullable=True))
        batch_op.create_foreign_key(
            "fk_generated_images_accepted_by_user_id_users",
            "users",
            ["accepted_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("generated_images") as batch_op:
        batch_op.drop_constraint(
            "fk_generated_images_accepted_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("accepted_by_user_id")
        batch_op.drop_column("accepted_at")
