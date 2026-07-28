"""add native agent article workflow

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-07-29 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l3m4n5o6p7q8"
down_revision: Union[str, None] = "k2l3m4n5o6p7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.add_column(
            sa.Column("workflow_phase", sa.String(length=80), nullable=True)
        )
        batch_op.add_column(
            sa.Column("workflow_checkpoint_json", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "workflow_revision",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.create_index(
            "ix_native_agent_runs_workflow_phase",
            ["workflow_phase"],
        )

    op.create_table(
        "native_agent_artifacts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("producer_role", sa.String(length=40), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_native_agent_artifacts_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["native_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "artifact_type",
            "version",
            name="uq_native_agent_artifacts_run_type_version",
        ),
    )
    op.create_index(
        "ix_native_agent_artifacts_run_id",
        "native_agent_artifacts",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_artifacts_artifact_type",
        "native_agent_artifacts",
        ["artifact_type"],
    )
    op.create_index(
        "ix_native_agent_artifacts_status",
        "native_agent_artifacts",
        ["status"],
    )
    op.create_index(
        "ix_native_agent_artifacts_run_type_version",
        "native_agent_artifacts",
        ["run_id", "artifact_type", "version"],
    )

    op.create_table(
        "native_agent_article_approvals",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("artifact_id", sa.String(length=32), nullable=False),
        sa.Column("artifact_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by_user_id", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["native_agent_artifacts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["native_agent_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id"),
    )
    op.create_index(
        "ix_native_agent_article_approvals_run_id",
        "native_agent_article_approvals",
        ["run_id"],
    )
    op.create_index(
        "ix_native_agent_article_approvals_status",
        "native_agent_article_approvals",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_native_agent_article_approvals_status",
        table_name="native_agent_article_approvals",
    )
    op.drop_index(
        "ix_native_agent_article_approvals_run_id",
        table_name="native_agent_article_approvals",
    )
    op.drop_table("native_agent_article_approvals")
    op.drop_index(
        "ix_native_agent_artifacts_run_type_version",
        table_name="native_agent_artifacts",
    )
    op.drop_index(
        "ix_native_agent_artifacts_status",
        table_name="native_agent_artifacts",
    )
    op.drop_index(
        "ix_native_agent_artifacts_artifact_type",
        table_name="native_agent_artifacts",
    )
    op.drop_index(
        "ix_native_agent_artifacts_run_id",
        table_name="native_agent_artifacts",
    )
    op.drop_table("native_agent_artifacts")
    with op.batch_alter_table("native_agent_runs") as batch_op:
        batch_op.drop_index("ix_native_agent_runs_workflow_phase")
        batch_op.drop_column("workflow_revision")
        batch_op.drop_column("workflow_checkpoint_json")
        batch_op.drop_column("workflow_phase")
