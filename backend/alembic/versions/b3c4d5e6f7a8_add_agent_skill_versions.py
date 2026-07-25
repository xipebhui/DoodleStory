"""add versioned agent skills

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-26 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


skill_status = sa.Enum(
    "draft",
    "published",
    "archived",
    name="agentskillstatus",
)


def upgrade() -> None:
    op.create_table(
        "agent_skills",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.String(length=32), nullable=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("draft_instructions", sa.Text(), nullable=False),
        sa.Column("draft_tool_names_json", sa.Text(), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("active_version_id", sa.String(length=32), nullable=True),
        sa.Column("status", skill_status, nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint(
            "draft_revision > 0",
            name="ck_agent_skills_draft_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "slug",
            name="uq_agent_skills_owner_slug",
        ),
    )
    op.create_index(
        "ix_agent_skills_owner_user_id",
        "agent_skills",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_agent_skills_status",
        "agent_skills",
        ["status"],
    )
    op.create_index(
        "ix_agent_skills_owner_updated",
        "agent_skills",
        ["owner_user_id", "updated_at"],
    )
    op.create_index(
        "uq_agent_skills_system_slug",
        "agent_skills",
        ["slug"],
        unique=True,
        sqlite_where=sa.text("owner_user_id IS NULL"),
        postgresql_where=sa.text("owner_user_id IS NULL"),
    )

    op.create_table(
        "agent_skill_versions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("skill_id", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("description_snapshot", sa.String(length=500), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("tool_names_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("publish_idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("published_by_user_id", sa.String(length=32), nullable=True),
        sa.Column("published_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint(
            "version > 0",
            name="ck_agent_skill_versions_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["agent_skills.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "skill_id",
            "publish_idempotency_key",
            name="uq_agent_skill_versions_publish_idempotency",
        ),
        sa.UniqueConstraint(
            "skill_id",
            "version",
            name="uq_agent_skill_versions_skill_version",
        ),
    )
    op.create_index(
        "ix_agent_skill_versions_skill_id",
        "agent_skill_versions",
        ["skill_id"],
    )

    with op.batch_alter_table("agent_skills") as batch_op:
        batch_op.create_foreign_key(
            "fk_agent_skills_active_version_id",
            "agent_skill_versions",
            ["active_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(
            sa.Column("skill_version_id", sa.String(length=32), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_agent_runs_skill_version_id",
            "agent_skill_versions",
            ["skill_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_agent_runs_skill_version_id",
            ["skill_version_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_index("ix_agent_runs_skill_version_id")
        batch_op.drop_constraint(
            "fk_agent_runs_skill_version_id",
            type_="foreignkey",
        )
        batch_op.drop_column("skill_version_id")

    with op.batch_alter_table("agent_skills") as batch_op:
        batch_op.drop_constraint(
            "fk_agent_skills_active_version_id",
            type_="foreignkey",
        )

    op.drop_index(
        "ix_agent_skill_versions_skill_id",
        table_name="agent_skill_versions",
    )
    op.drop_table("agent_skill_versions")
    op.drop_index("uq_agent_skills_system_slug", table_name="agent_skills")
    op.drop_index("ix_agent_skills_owner_updated", table_name="agent_skills")
    op.drop_index("ix_agent_skills_status", table_name="agent_skills")
    op.drop_index("ix_agent_skills_owner_user_id", table_name="agent_skills")
    op.drop_table("agent_skills")
    skill_status.drop(op.get_bind(), checkfirst=True)
