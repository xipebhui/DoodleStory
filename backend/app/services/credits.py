import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    CreditActivationCode,
    CreditActivationCodeRedemption,
    CreditTransaction,
    User,
    UserCreditAccount,
)
from app.models.enums import CreditTransactionType

DEFAULT_NEW_USER_CREDITS = 30
IMAGE_CREDIT_COST = 1


@dataclass(frozen=True)
class CreditError(Exception):
    detail: str

    def __str__(self) -> str:
        return self.detail


class InsufficientCreditsError(CreditError):
    pass


class ActivationCodeError(CreditError):
    pass


def normalize_activation_code(code: str) -> str:
    return "".join(code.strip().upper().split())


def hash_activation_code(code: str) -> str:
    return hashlib.sha256(normalize_activation_code(code).encode("utf-8")).hexdigest()


def generate_activation_code_plaintext() -> str:
    token = secrets.token_urlsafe(18).replace("-", "").replace("_", "").upper()
    return f"DS-{token[:4]}-{token[4:8]}-{token[8:12]}-{token[12:16]}"


def load_credit_account_for_update(db: Session, user_id: str) -> UserCreditAccount | None:
    return db.scalar(
        select(UserCreditAccount)
        .where(UserCreditAccount.user_id == user_id)
        .with_for_update()
    )


def ensure_credit_account(
    db: Session,
    user_id: str,
    *,
    initial_balance: int = 0,
    note: str | None = None,
) -> UserCreditAccount:
    account = load_credit_account_for_update(db, user_id)
    if account:
        return account
    account = UserCreditAccount(user_id=user_id, balance=initial_balance, reserved_balance=0)
    db.add(account)
    db.flush()
    if initial_balance:
        record_transaction(
            db,
            account=account,
            transaction_type=CreditTransactionType.initial_grant,
            amount=initial_balance,
            balance_before=0,
            reserved_balance_before=0,
            note=note,
        )
    return account


def record_transaction(
    db: Session,
    *,
    account: UserCreditAccount,
    transaction_type: CreditTransactionType,
    amount: int,
    balance_before: int,
    reserved_balance_before: int,
    admin_user_id: str | None = None,
    task_id: str | None = None,
    panel_id: str | None = None,
    generated_image_id: str | None = None,
    style_test_id: str | None = None,
    character_appearance_id: str | None = None,
    activation_code_id: str | None = None,
    note: str | None = None,
) -> CreditTransaction:
    transaction = CreditTransaction(
        user_id=account.user_id,
        transaction_type=transaction_type,
        amount=amount,
        balance_before=balance_before,
        balance_after=account.balance,
        reserved_balance_before=reserved_balance_before,
        reserved_balance_after=account.reserved_balance,
        admin_user_id=admin_user_id,
        task_id=task_id,
        panel_id=panel_id,
        generated_image_id=generated_image_id,
        style_test_id=style_test_id,
        character_appearance_id=character_appearance_id,
        activation_code_id=activation_code_id,
        note=note,
    )
    db.add(transaction)
    db.flush()
    return transaction


def grant_initial_credits(db: Session, user: User, amount: int = DEFAULT_NEW_USER_CREDITS) -> UserCreditAccount:
    return ensure_credit_account(
        db,
        user.id,
        initial_balance=amount,
        note="新用户注册默认积分",
    )


def adjust_user_credits_by_admin(
    db: Session,
    *,
    user_id: str,
    admin_user_id: str,
    amount: int,
    note: str,
) -> CreditTransaction:
    if amount == 0:
        raise CreditError("积分调整数量不能为 0")
    account = ensure_credit_account(db, user_id)
    balance_before = account.balance
    reserved_before = account.reserved_balance
    next_balance = account.balance + amount
    if next_balance < 0:
        raise InsufficientCreditsError("用户可用积分不足，不能扣减到负数")
    account.balance = next_balance
    return record_transaction(
        db,
        account=account,
        transaction_type=CreditTransactionType.admin_adjustment,
        amount=amount,
        balance_before=balance_before,
        reserved_balance_before=reserved_before,
        admin_user_id=admin_user_id,
        note=note,
    )


def reserve_image_credit(
    db: Session,
    *,
    user_id: str,
    task_id: str | None = None,
    panel_id: str | None = None,
    generated_image_id: str | None = None,
    style_test_id: str | None = None,
    character_appearance_id: str | None = None,
    note: str | None = None,
) -> CreditTransaction:
    account = ensure_credit_account(db, user_id)
    if account.balance < IMAGE_CREDIT_COST:
        raise InsufficientCreditsError("积分不足，无法生成图片")
    balance_before = account.balance
    reserved_before = account.reserved_balance
    account.balance -= IMAGE_CREDIT_COST
    account.reserved_balance += IMAGE_CREDIT_COST
    return record_transaction(
        db,
        account=account,
        transaction_type=CreditTransactionType.image_generation_reserve,
        amount=-IMAGE_CREDIT_COST,
        balance_before=balance_before,
        reserved_balance_before=reserved_before,
        task_id=task_id,
        panel_id=panel_id,
        generated_image_id=generated_image_id,
        style_test_id=style_test_id,
        character_appearance_id=character_appearance_id,
        note=note,
    )


def charge_reserved_image_credit(
    db: Session,
    *,
    user_id: str,
    task_id: str | None = None,
    panel_id: str | None = None,
    generated_image_id: str | None = None,
    style_test_id: str | None = None,
    character_appearance_id: str | None = None,
    note: str | None = None,
) -> CreditTransaction:
    account = ensure_credit_account(db, user_id)
    if account.reserved_balance < IMAGE_CREDIT_COST:
        raise CreditError("图片生成积分占用不存在，无法扣费")
    balance_before = account.balance
    reserved_before = account.reserved_balance
    account.reserved_balance -= IMAGE_CREDIT_COST
    return record_transaction(
        db,
        account=account,
        transaction_type=CreditTransactionType.image_generation_charge,
        amount=-IMAGE_CREDIT_COST,
        balance_before=balance_before,
        reserved_balance_before=reserved_before,
        task_id=task_id,
        panel_id=panel_id,
        generated_image_id=generated_image_id,
        style_test_id=style_test_id,
        character_appearance_id=character_appearance_id,
        note=note,
    )


def release_reserved_image_credit(
    db: Session,
    *,
    user_id: str,
    task_id: str | None = None,
    panel_id: str | None = None,
    generated_image_id: str | None = None,
    style_test_id: str | None = None,
    character_appearance_id: str | None = None,
    note: str | None = None,
) -> CreditTransaction:
    account = ensure_credit_account(db, user_id)
    if account.reserved_balance < IMAGE_CREDIT_COST:
        raise CreditError("图片生成积分占用不存在，无法释放")
    balance_before = account.balance
    reserved_before = account.reserved_balance
    account.balance += IMAGE_CREDIT_COST
    account.reserved_balance -= IMAGE_CREDIT_COST
    return record_transaction(
        db,
        account=account,
        transaction_type=CreditTransactionType.image_generation_release,
        amount=IMAGE_CREDIT_COST,
        balance_before=balance_before,
        reserved_balance_before=reserved_before,
        task_id=task_id,
        panel_id=panel_id,
        generated_image_id=generated_image_id,
        style_test_id=style_test_id,
        character_appearance_id=character_appearance_id,
        note=note,
    )


def create_activation_codes(
    db: Session,
    *,
    admin_user_id: str,
    credit_amount: int,
    count: int,
    expires_at: datetime | None,
    note: str | None,
) -> list[tuple[CreditActivationCode, str]]:
    created: list[tuple[CreditActivationCode, str]] = []
    for _ in range(count):
        plaintext = generate_activation_code_plaintext()
        code = CreditActivationCode(
            code_hash=hash_activation_code(plaintext),
            code_prefix=normalize_activation_code(plaintext)[:10],
            credit_amount=credit_amount,
            expires_at=expires_at,
            note=note,
            created_by_admin_id=admin_user_id,
        )
        db.add(code)
        db.flush()
        created.append((code, plaintext))
    return created


def redeem_activation_code(db: Session, *, user_id: str, code: str) -> CreditTransaction:
    normalized = normalize_activation_code(code)
    if not normalized:
        raise ActivationCodeError("激活码不能为空")
    activation_code = db.scalar(
        select(CreditActivationCode)
        .where(CreditActivationCode.code_hash == hash_activation_code(normalized))
        .with_for_update()
    )
    if not activation_code:
        raise ActivationCodeError("激活码不存在")
    if activation_code.disabled_at is not None:
        raise ActivationCodeError("激活码已禁用")
    if activation_code.redeemed_at is not None:
        raise ActivationCodeError("激活码已被兑换")
    if activation_code.expires_at is not None and activation_code.expires_at < datetime.utcnow():
        raise ActivationCodeError("激活码已过期")

    account = ensure_credit_account(db, user_id)
    balance_before = account.balance
    reserved_before = account.reserved_balance
    account.balance += activation_code.credit_amount
    activation_code.redeemed_by_user_id = user_id
    activation_code.redeemed_at = datetime.utcnow()
    transaction = record_transaction(
        db,
        account=account,
        transaction_type=CreditTransactionType.activation_code_redeem,
        amount=activation_code.credit_amount,
        balance_before=balance_before,
        reserved_balance_before=reserved_before,
        activation_code_id=activation_code.id,
        note=f"兑换激活码 {activation_code.code_prefix}",
    )
    db.add(
        CreditActivationCodeRedemption(
            activation_code_id=activation_code.id,
            user_id=user_id,
            transaction_id=transaction.id,
        )
    )
    db.flush()
    return transaction
