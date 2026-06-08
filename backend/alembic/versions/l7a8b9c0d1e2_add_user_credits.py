"""add user credits

Revision ID: l7a8b9c0d1e2
Revises: k6f7a8b9c0d1
Create Date: 2026-06-08 22:10:00.000000
"""

from datetime import datetime
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "l7a8b9c0d1e2"
down_revision: Union[str, None] = "k6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    tables = table_names()
    if "user_credit_accounts" not in tables:
        op.create_table(
            "user_credit_accounts",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.String(length=32), nullable=False),
            sa.Column("balance", sa.Integer(), nullable=False),
            sa.Column("reserved_balance", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("balance >= 0", name="ck_user_credit_accounts_balance_non_negative"),
            sa.CheckConstraint("reserved_balance >= 0", name="ck_user_credit_accounts_reserved_non_negative"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index("ix_user_credit_accounts_user_id", "user_credit_accounts", ["user_id"], unique=True)

    if "credit_activation_codes" not in tables:
        op.create_table(
            "credit_activation_codes",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("code_prefix", sa.String(length=12), nullable=False),
            sa.Column("credit_amount", sa.Integer(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("disabled_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_admin_id", sa.String(length=32), nullable=True),
            sa.Column("redeemed_by_user_id", sa.String(length=32), nullable=True),
            sa.Column("redeemed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("credit_amount > 0", name="ck_credit_activation_codes_credit_amount_positive"),
            sa.ForeignKeyConstraint(["created_by_admin_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["redeemed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code_hash"),
        )
        op.create_index("ix_credit_activation_codes_code_hash", "credit_activation_codes", ["code_hash"], unique=True)
        op.create_index("ix_credit_activation_codes_code_prefix", "credit_activation_codes", ["code_prefix"], unique=False)
        op.create_index("ix_credit_activation_codes_created_by_admin_id", "credit_activation_codes", ["created_by_admin_id"], unique=False)
        op.create_index("ix_credit_activation_codes_expires_at", "credit_activation_codes", ["expires_at"], unique=False)
        op.create_index("ix_credit_activation_codes_redeemed_by_user_id", "credit_activation_codes", ["redeemed_by_user_id"], unique=False)

    if "credit_transactions" not in tables:
        op.create_table(
            "credit_transactions",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.String(length=32), nullable=False),
            sa.Column("transaction_type", sa.String(length=40), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("balance_before", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("reserved_balance_before", sa.Integer(), nullable=False),
            sa.Column("reserved_balance_after", sa.Integer(), nullable=False),
            sa.Column("admin_user_id", sa.String(length=32), nullable=True),
            sa.Column("task_id", sa.String(length=32), nullable=True),
            sa.Column("panel_id", sa.String(length=32), nullable=True),
            sa.Column("generated_image_id", sa.String(length=32), nullable=True),
            sa.Column("style_test_id", sa.String(length=32), nullable=True),
            sa.Column("character_appearance_id", sa.String(length=32), nullable=True),
            sa.Column("activation_code_id", sa.String(length=32), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("amount != 0", name="ck_credit_transactions_amount_non_zero"),
            sa.CheckConstraint("balance_after >= 0", name="ck_credit_transactions_balance_after_non_negative"),
            sa.CheckConstraint("reserved_balance_after >= 0", name="ck_credit_transactions_reserved_after_non_negative"),
            sa.ForeignKeyConstraint(["activation_code_id"], ["credit_activation_codes.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["character_appearance_id"], ["task_character_appearances.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["generated_image_id"], ["generated_images.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["panel_id"], ["task_panels.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["style_test_id"], ["style_tests.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["task_id"], ["generation_tasks.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in [
            "activation_code_id",
            "admin_user_id",
            "character_appearance_id",
            "generated_image_id",
            "panel_id",
            "style_test_id",
            "task_id",
            "transaction_type",
            "user_id",
        ]:
            op.create_index(f"ix_credit_transactions_{column}", "credit_transactions", [column], unique=False)

    if "credit_activation_code_redemptions" not in tables:
        op.create_table(
            "credit_activation_code_redemptions",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("activation_code_id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.String(length=32), nullable=False),
            sa.Column("transaction_id", sa.String(length=32), nullable=False),
            sa.Column("redeemed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["activation_code_id"], ["credit_activation_codes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["transaction_id"], ["credit_transactions.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("activation_code_id"),
            sa.UniqueConstraint("transaction_id"),
        )
        op.create_index(
            "ix_credit_activation_code_redemptions_activation_code_id",
            "credit_activation_code_redemptions",
            ["activation_code_id"],
            unique=True,
        )
        op.create_index("ix_credit_activation_code_redemptions_redeemed_at", "credit_activation_code_redemptions", ["redeemed_at"], unique=False)
        op.create_index(
            "ix_credit_activation_code_redemptions_user_id",
            "credit_activation_code_redemptions",
            ["user_id"],
            unique=False,
        )

    bind = op.get_bind()
    users = bind.execute(sa.text("select id from users")).fetchall()
    existing_accounts = {
        row[0] for row in bind.execute(sa.text("select user_id from user_credit_accounts")).fetchall()
    }
    now = datetime.utcnow()
    account_table = sa.table(
        "user_credit_accounts",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("balance", sa.Integer),
        sa.column("reserved_balance", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    transaction_table = sa.table(
        "credit_transactions",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("transaction_type", sa.String),
        sa.column("amount", sa.Integer),
        sa.column("balance_before", sa.Integer),
        sa.column("balance_after", sa.Integer),
        sa.column("reserved_balance_before", sa.Integer),
        sa.column("reserved_balance_after", sa.Integer),
        sa.column("note", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    accounts = []
    transactions = []
    for (user_id,) in users:
        if user_id in existing_accounts:
            continue
        accounts.append(
            {
                "id": uuid4().hex,
                "user_id": user_id,
                "balance": 1000,
                "reserved_balance": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        transactions.append(
            {
                "id": uuid4().hex,
                "user_id": user_id,
                "transaction_type": "initial_grant",
                "amount": 1000,
                "balance_before": 0,
                "balance_after": 1000,
                "reserved_balance_before": 0,
                "reserved_balance_after": 0,
                "note": "Sprint 44 上线时为已注册用户初始化积分",
                "created_at": now,
                "updated_at": now,
            }
        )
    if accounts:
        op.bulk_insert(account_table, accounts)
    if transactions:
        op.bulk_insert(transaction_table, transactions)


def downgrade() -> None:
    for table_name in [
        "credit_activation_code_redemptions",
        "credit_transactions",
        "credit_activation_codes",
        "user_credit_accounts",
    ]:
        if table_name in table_names():
            op.drop_table(table_name)
