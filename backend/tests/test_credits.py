import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.credits import admin_credit_transaction_rows, admin_usage_for_period, my_credits, transaction_rows_for_user, usage_points_for_user
from app.api.pagination import Pagination
from app.api.styles import create_style_test
from app.core.database import Base
from app.models.entities import CreditTransaction, Style, User
from app.models.enums import CreditTransactionType, StorageBackend, StyleReferenceMode, StyleStatus, UserRole, WorkflowStatus
from app.schemas.style import StyleTestCreate
from app.services.credits import (
    InsufficientCreditsError,
    adjust_user_credits_by_admin,
    charge_reserved_image_credit,
    create_activation_codes,
    grant_initial_credits,
    redeem_activation_code,
    release_reserved_image_credit,
    reserve_image_credit,
)
from app.services.image_generation import GeneratedImageFile, ImageProviderResponseError


class CreditsTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_new_user_initial_credits(self) -> None:
        db = self.Session()
        user = User(email="new@example.com", password_hash="hash")
        db.add(user)
        db.flush()

        account = grant_initial_credits(db, user)
        db.commit()

        self.assertEqual(30, account.balance)
        transaction = db.scalar(select(CreditTransaction).where(CreditTransaction.user_id == user.id))
        self.assertIsNotNone(transaction)
        self.assertEqual(CreditTransactionType.initial_grant, transaction.transaction_type)
        self.assertEqual(30, transaction.amount)

    def test_reserve_charge_and_release_image_credit(self) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash")
        db.add(user)
        db.flush()
        grant_initial_credits(db, user, amount=2)
        db.commit()

        reserve_image_credit(db, user_id=user.id, note="占用")
        db.commit()
        db.refresh(user.credit_account)
        self.assertEqual(1, user.credit_account.balance)
        self.assertEqual(1, user.credit_account.reserved_balance)

        release_reserved_image_credit(db, user_id=user.id, note="释放")
        db.commit()
        db.refresh(user.credit_account)
        self.assertEqual(2, user.credit_account.balance)
        self.assertEqual(0, user.credit_account.reserved_balance)

        reserve_image_credit(db, user_id=user.id, note="再次占用")
        charge_reserved_image_credit(db, user_id=user.id, note="扣费")
        db.commit()
        db.refresh(user.credit_account)
        self.assertEqual(1, user.credit_account.balance)
        self.assertEqual(0, user.credit_account.reserved_balance)

    def test_insufficient_credit_blocks_reserve(self) -> None:
        db = self.Session()
        user = User(email="empty@example.com", password_hash="hash")
        db.add(user)
        db.flush()
        grant_initial_credits(db, user, amount=0)
        db.commit()

        with self.assertRaises(InsufficientCreditsError):
            reserve_image_credit(db, user_id=user.id)

    def test_usage_points_only_count_successful_charges(self) -> None:
        db = self.Session()
        user = User(email="usage@example.com", password_hash="hash")
        db.add(user)
        db.flush()
        grant_initial_credits(db, user, amount=5)

        reserve_image_credit(db, user_id=user.id, note="占用")
        recent_charge = charge_reserved_image_credit(db, user_id=user.id, note="扣费")
        reserve_image_credit(db, user_id=user.id, note="占用")
        old_charge = charge_reserved_image_credit(db, user_id=user.id, note="旧扣费")
        reserve_image_credit(db, user_id=user.id, note="临时占用")
        release_reserved_image_credit(db, user_id=user.id, note="释放")
        old_charge.created_at = datetime.utcnow() - timedelta(days=10)
        recent_charge.created_at = datetime.utcnow()
        db.commit()

        self.assertEqual(24, len(usage_points_for_user(db, user.id, 1)))
        self.assertEqual(1, sum(point.spent_credits for point in usage_points_for_user(db, user.id, 1)))
        self.assertEqual(7, len(usage_points_for_user(db, user.id, 7)))
        self.assertEqual(1, sum(point.spent_credits for point in usage_points_for_user(db, user.id, 7)))
        self.assertEqual(30, len(usage_points_for_user(db, user.id, 30)))
        self.assertEqual(2, sum(point.spent_credits for point in usage_points_for_user(db, user.id, 30)))

    def test_credit_transactions_are_lazy_paginated_and_filterable(self) -> None:
        db = self.Session()
        admin = User(email="admin@example.com", password_hash="hash", role=UserRole.admin)
        user = User(email="transactions@example.com", password_hash="hash")
        db.add_all([admin, user])
        db.flush()
        grant_initial_credits(db, user, amount=5)
        adjust_user_credits_by_admin(db, user_id=user.id, admin_user_id=admin.id, amount=5, note="重置积分")
        reserve_image_credit(db, user_id=user.id, note="占用")
        charge_reserved_image_credit(db, user_id=user.id, note="成功扣费")
        reserve_image_credit(db, user_id=user.id, note="临时占用")
        release_reserved_image_credit(db, user_id=user.id, note="失败释放")
        db.commit()

        overview = my_credits(user=user, db=db)
        self.assertEqual([], overview.data.recent_transactions)

        first_page, row_count = transaction_rows_for_user(
            db,
            user_id=user.id,
            pagination=Pagination(limit=2, offset=0),
        )
        self.assertEqual(2, len(first_page))
        self.assertEqual(3, row_count)

        spent_rows, spent_count = transaction_rows_for_user(
            db,
            user_id=user.id,
            pagination=Pagination(limit=10, offset=0),
            transaction_filter="spent",
        )
        self.assertEqual(1, spent_count)
        self.assertEqual([CreditTransactionType.image_generation_charge], [row.transaction_type for row in spent_rows])

        reset_rows, reset_count = transaction_rows_for_user(
            db,
            user_id=user.id,
            pagination=Pagination(limit=10, offset=0),
            transaction_filter="reset",
        )
        self.assertEqual(1, reset_count)
        self.assertEqual([CreditTransactionType.admin_adjustment], [row.transaction_type for row in reset_rows])

    def test_admin_usage_dashboard_can_filter_by_user(self) -> None:
        db = self.Session()
        user_a = User(email="a@example.com", password_hash="hash")
        user_b = User(email="b@example.com", password_hash="hash")
        db.add_all([user_a, user_b])
        db.flush()
        grant_initial_credits(db, user_a, amount=10)
        grant_initial_credits(db, user_b, amount=10)
        for user in [user_a, user_a, user_b]:
            reserve_image_credit(db, user_id=user.id, note="占用")
            charge_reserved_image_credit(db, user_id=user.id, note="扣费")
        reserve_image_credit(db, user_id=user_b.id, note="临时占用")
        release_reserved_image_credit(db, user_id=user_b.id, note="失败释放")
        db.commit()

        all_usage = admin_usage_for_period(db, days=7)
        self.assertEqual(3, all_usage.summary.total_spent_credits)
        self.assertEqual(3, all_usage.summary.transaction_count)
        self.assertEqual(2, all_usage.summary.active_user_count)
        self.assertEqual(7, len(all_usage.points))
        self.assertEqual(3, sum(point.spent_credits for point in all_usage.points))

        hourly_usage = admin_usage_for_period(db, days=1)
        self.assertEqual(24, len(hourly_usage.points))
        self.assertEqual(3, sum(point.spent_credits for point in hourly_usage.points))

        user_usage = admin_usage_for_period(db, days=7, user_id=user_a.id)
        self.assertEqual(2, user_usage.summary.total_spent_credits)
        self.assertEqual(2, user_usage.summary.transaction_count)
        self.assertEqual(1, user_usage.summary.active_user_count)

        first_page, row_count = admin_credit_transaction_rows(db, pagination=Pagination(limit=2, offset=0))
        self.assertEqual(2, len(first_page))
        self.assertEqual(3, row_count)
        self.assertTrue(all(item.transaction_type == CreditTransactionType.image_generation_charge for item in first_page))
        self.assertTrue(all(item.user_email in {"a@example.com", "b@example.com"} for item in first_page))

    def test_admin_adjustment_and_activation_code_redeem(self) -> None:
        db = self.Session()
        admin = User(email="admin@example.com", password_hash="hash", role=UserRole.admin)
        user = User(email="user@example.com", password_hash="hash")
        db.add_all([admin, user])
        db.flush()
        grant_initial_credits(db, user, amount=30)
        adjust_user_credits_by_admin(db, user_id=user.id, admin_user_id=admin.id, amount=70, note="补积分")
        code, plaintext = create_activation_codes(
            db,
            admin_user_id=admin.id,
            credit_amount=50,
            count=1,
            expires_at=None,
            note="测试码",
        )[0]
        redeem_activation_code(db, user_id=user.id, code=plaintext)
        db.commit()

        db.refresh(user.credit_account)
        self.assertEqual(150, user.credit_account.balance)
        self.assertIsNotNone(code.redeemed_at)
        with self.assertRaises(Exception):
            redeem_activation_code(db, user_id=user.id, code=plaintext)

    def test_style_test_credit_success_and_provider_failure_release(self) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash")
        style = Style(
            name="测试风格",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="9:16",
            style_reference_mode=StyleReferenceMode.prompt,
            style_prompt="水彩风",
        )
        db.add_all([user, style])
        db.flush()
        grant_initial_credits(db, user, amount=2)
        db.commit()

        generated = GeneratedImageFile(
            storage_backend=StorageBackend.local,
            storage_key="generated/test.png",
            public_url=None,
            original_filename="test.png",
            content_type="image/png",
            byte_size=10,
            checksum_sha256="x",
            provider_request_id="req_1",
        )
        with patch("app.api.styles.generate_xg_image", return_value=generated) as provider:
            result = create_style_test(style.id, StyleTestCreate(test_text="一只猫"), user, db)

        db.refresh(user.credit_account)
        self.assertEqual(WorkflowStatus.succeeded, result.data.status)
        self.assertEqual(1, user.credit_account.balance)
        self.assertEqual(0, user.credit_account.reserved_balance)
        self.assertEqual(1, provider.call_count)

        with patch("app.api.styles.generate_xg_image", side_effect=ImageProviderResponseError("provider failed")):
            result = create_style_test(style.id, StyleTestCreate(test_text="一只狗"), user, db)

        db.refresh(user.credit_account)
        self.assertEqual(WorkflowStatus.failed, result.data.status)
        self.assertEqual(1, user.credit_account.balance)
        self.assertEqual(0, user.credit_account.reserved_balance)

    def test_style_test_insufficient_credit_does_not_call_provider(self) -> None:
        db = self.Session()
        user = User(email="empty@example.com", password_hash="hash")
        style = Style(
            name="无积分风格",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="9:16",
            style_reference_mode=StyleReferenceMode.prompt,
            style_prompt="水彩风",
        )
        db.add_all([user, style])
        db.flush()
        grant_initial_credits(db, user, amount=0)
        db.commit()

        with patch("app.api.styles.generate_xg_image") as provider:
            result = create_style_test(style.id, StyleTestCreate(test_text="一只猫"), user, db)

        self.assertEqual(WorkflowStatus.failed, result.data.status)
        self.assertEqual("InsufficientCreditsError", result.data.error_code)
        self.assertEqual(0, provider.call_count)


if __name__ == "__main__":
    unittest.main()
