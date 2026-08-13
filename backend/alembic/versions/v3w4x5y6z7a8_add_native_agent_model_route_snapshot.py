"""add native agent model route snapshot

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-08-13 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v3w4x5y6z7a8"
down_revision: Union[str, None] = "u2v3w4x5y6z7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.add_column(
            sa.Column("model_route_snapshot", sa.String(length=80), nullable=True)
        )
        batch_op.add_column(
            sa.Column("model_provider_snapshot", sa.String(length=80), nullable=True)
        )
        batch_op.add_column(
            sa.Column("model_api_shape_snapshot", sa.String(length=80), nullable=True)
        )

    op.execute(
        sa.text(
            "UPDATE native_agent_runs SET "
            "model_route_snapshot = 'huomiao_responses', "
            "model_provider_snapshot = 'huomiao', "
            "model_api_shape_snapshot = 'responses'"
        )
    )

    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.alter_column(
            "model_route_snapshot",
            existing_type=sa.String(length=80),
            nullable=False,
        )
        batch_op.alter_column(
            "model_provider_snapshot",
            existing_type=sa.String(length=80),
            nullable=False,
        )
        batch_op.alter_column(
            "model_api_shape_snapshot",
            existing_type=sa.String(length=80),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.drop_column("model_api_shape_snapshot")
        batch_op.drop_column("model_provider_snapshot")
        batch_op.drop_column("model_route_snapshot")
