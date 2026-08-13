"""add native agent model call evidence

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
Create Date: 2026-08-13 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w4x5y6z7a8b9"
down_revision: Union[str, None] = "v3w4x5y6z7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("native_agent_steps") as batch_op:
        batch_op.add_column(sa.Column("model_call_id", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("model_provider", sa.String(80), nullable=True))
        batch_op.add_column(sa.Column("model_api_shape", sa.String(80), nullable=True))
        batch_op.add_column(sa.Column("model_name", sa.String(160), nullable=True))
        batch_op.add_column(
            sa.Column("provider_response_id", sa.String(255), nullable=True)
        )
        batch_op.add_column(sa.Column("execution_attempt", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("model_call_ordinal", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("converted_message_count", sa.Integer(), nullable=True)
        )
        batch_op.add_column(sa.Column("latency_ms", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_native_agent_steps_model_call_id",
            ["model_call_id"],
        )
        batch_op.create_check_constraint(
            "ck_native_agent_steps_execution_attempt_positive",
            "execution_attempt IS NULL OR execution_attempt > 0",
        )
        batch_op.create_check_constraint(
            "ck_native_agent_steps_model_call_ordinal_positive",
            "model_call_ordinal IS NULL OR model_call_ordinal > 0",
        )
        batch_op.create_check_constraint(
            "ck_native_agent_steps_message_count_non_negative",
            "converted_message_count IS NULL OR converted_message_count >= 0",
        )
        batch_op.create_check_constraint(
            "ck_native_agent_steps_latency_non_negative",
            "latency_ms IS NULL OR latency_ms >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("native_agent_steps") as batch_op:
        batch_op.drop_constraint(
            "ck_native_agent_steps_latency_non_negative",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_native_agent_steps_message_count_non_negative",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_native_agent_steps_model_call_ordinal_positive",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_native_agent_steps_execution_attempt_positive",
            type_="check",
        )
        batch_op.drop_constraint(
            "uq_native_agent_steps_model_call_id",
            type_="unique",
        )
        batch_op.drop_column("latency_ms")
        batch_op.drop_column("converted_message_count")
        batch_op.drop_column("model_call_ordinal")
        batch_op.drop_column("execution_attempt")
        batch_op.drop_column("provider_response_id")
        batch_op.drop_column("model_name")
        batch_op.drop_column("model_api_shape")
        batch_op.drop_column("model_provider")
        batch_op.drop_column("model_call_id")
