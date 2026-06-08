from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CreditTransactionType, UserRole
from app.schemas.common import TimestampFields


class CreditAccountRead(TimestampFields):
    user_id: str
    balance: int
    reserved_balance: int

    @property
    def available_balance(self) -> int:
        return self.balance


class CreditTransactionRead(TimestampFields):
    id: str
    user_id: str
    transaction_type: CreditTransactionType
    amount: int
    balance_before: int
    balance_after: int
    reserved_balance_before: int
    reserved_balance_after: int
    admin_user_id: str | None
    task_id: str | None
    panel_id: str | None
    generated_image_id: str | None
    style_test_id: str | None
    character_appearance_id: str | None
    activation_code_id: str | None
    note: str | None


class CreditOverviewRead(BaseModel):
    account: CreditAccountRead
    recent_transactions: list[CreditTransactionRead]


class CreditRedeemRequest(BaseModel):
    code: str = Field(min_length=6, max_length=80)


class AdminUserCreditSummary(BaseModel):
    id: str
    email: str
    display_name: str | None
    role: UserRole
    balance: int
    reserved_balance: int
    task_count: int
    succeeded_image_count: int
    spent_credits: int
    created_at: datetime
    updated_at: datetime


class AdminUserCreditDetail(BaseModel):
    user: AdminUserCreditSummary
    recent_transactions: list[CreditTransactionRead]


class AdminCreditAdjustmentRequest(BaseModel):
    amount: int = Field(ge=-100000, le=100000)
    note: str = Field(min_length=1, max_length=500)


class ActivationCodeCreateRequest(BaseModel):
    credit_amount: int = Field(ge=1, le=100000)
    count: int = Field(default=1, ge=1, le=200)
    expires_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)


class ActivationCodeCreatedRead(BaseModel):
    id: str
    code: str
    credit_amount: int
    expires_at: datetime | None
    note: str | None


class ActivationCodeRead(TimestampFields):
    id: str
    code_prefix: str
    credit_amount: int
    note: str | None
    expires_at: datetime | None
    disabled_at: datetime | None
    created_by_admin_id: str | None
    redeemed_by_user_id: str | None
    redeemed_at: datetime | None
