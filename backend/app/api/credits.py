from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.pagination import Pagination, build_page, get_pagination
from app.core.database import get_db
from app.models.entities import (
    CreditActivationCode,
    CreditTransaction,
    GeneratedImage,
    GenerationTask,
    User,
    UserCreditAccount,
)
from app.models.enums import CreditTransactionType, GeneratedImageStatus, UserRole
from app.schemas.common import ApiData, ApiList
from app.schemas.credits import (
    ActivationCodeCreateRequest,
    ActivationCodeCreatedRead,
    ActivationCodeRead,
    AdminCreditAdjustmentRequest,
    AdminUserCreditDetail,
    AdminUserCreditSummary,
    CreditOverviewRead,
    CreditRedeemRequest,
    CreditTransactionRead,
    CreditUsagePointRead,
)
from app.services.credits import (
    ActivationCodeError,
    CreditError,
    adjust_user_credits_by_admin,
    create_activation_codes,
    ensure_credit_account,
    redeem_activation_code,
)

router = APIRouter(tags=["credits"])


def require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")


def recent_transactions_for_user(db: Session, user_id: str, limit: int = 20) -> list[CreditTransaction]:
    return db.scalars(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(limit)
    ).all()


def transaction_filter_condition(transaction_filter: str):
    if transaction_filter == "spent":
        return CreditTransaction.transaction_type == CreditTransactionType.image_generation_charge
    if transaction_filter == "reset":
        return CreditTransaction.transaction_type == CreditTransactionType.admin_adjustment
    if transaction_filter != "all":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="积分流水筛选不合法")
    return None


def transaction_rows_for_user(
    db: Session,
    *,
    user_id: str,
    pagination: Pagination,
    transaction_filter: str = "all",
) -> tuple[list[CreditTransaction], int]:
    statement = select(CreditTransaction).where(CreditTransaction.user_id == user_id)
    condition = transaction_filter_condition(transaction_filter)
    if condition is not None:
        statement = statement.where(condition)
    transactions = db.scalars(
        statement
        .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    ).all()
    return transactions[: pagination.limit], len(transactions)


def usage_points_for_user(db: Session, user_id: str, days: int) -> list[CreditUsagePointRead]:
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    if days == 1:
        bucket_count = 24
        bucket_delta = timedelta(hours=1)
        start = now - timedelta(hours=bucket_count - 1)
    else:
        bucket_count = days
        bucket_delta = timedelta(days=1)
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=bucket_count - 1)

    buckets = {start + bucket_delta * index: 0 for index in range(bucket_count)}
    transactions = db.scalars(
        select(CreditTransaction).where(
            CreditTransaction.user_id == user_id,
            CreditTransaction.transaction_type == CreditTransactionType.image_generation_charge,
            CreditTransaction.created_at >= start,
        )
    ).all()
    for transaction in transactions:
        created_at = transaction.created_at.replace(tzinfo=None)
        if days == 1:
            bucket_start = created_at.replace(minute=0, second=0, microsecond=0)
        else:
            bucket_start = created_at.replace(hour=0, minute=0, second=0, microsecond=0)
        if bucket_start in buckets:
            buckets[bucket_start] += max(0, -transaction.amount)

    return [
        CreditUsagePointRead(
            label=bucket_start.strftime("%H:00") if days == 1 else bucket_start.strftime("%m-%d"),
            spent_credits=spent,
            started_at=bucket_start,
        )
        for bucket_start, spent in buckets.items()
    ]


def user_summary_rows(
    db: Session,
    *,
    pagination: Pagination,
    query: str | None = None,
    user_id: str | None = None,
) -> tuple[list[AdminUserCreditSummary], int]:
    task_counts = (
        select(
            GenerationTask.owner_user_id.label("user_id"),
            func.count(GenerationTask.id).label("task_count"),
        )
        .group_by(GenerationTask.owner_user_id)
        .subquery()
    )
    image_counts = (
        select(
            GenerationTask.owner_user_id.label("user_id"),
            func.count(GeneratedImage.id).label("succeeded_image_count"),
        )
        .join(GeneratedImage, GeneratedImage.task_id == GenerationTask.id)
        .where(GeneratedImage.status == GeneratedImageStatus.succeeded)
        .group_by(GenerationTask.owner_user_id)
        .subquery()
    )
    spent_counts = (
        select(
            CreditTransaction.user_id.label("user_id"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            CreditTransaction.transaction_type == CreditTransactionType.image_generation_charge,
                            -CreditTransaction.amount,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("spent_credits"),
        )
        .group_by(CreditTransaction.user_id)
        .subquery()
    )
    statement = (
        select(
            User.id,
            User.email,
            User.display_name,
            User.role,
            User.created_at,
            User.updated_at,
            func.coalesce(UserCreditAccount.balance, 0).label("balance"),
            func.coalesce(UserCreditAccount.reserved_balance, 0).label("reserved_balance"),
            func.coalesce(task_counts.c.task_count, 0).label("task_count"),
            func.coalesce(image_counts.c.succeeded_image_count, 0).label("succeeded_image_count"),
            func.coalesce(spent_counts.c.spent_credits, 0).label("spent_credits"),
        )
        .outerjoin(UserCreditAccount, UserCreditAccount.user_id == User.id)
        .outerjoin(task_counts, task_counts.c.user_id == User.id)
        .outerjoin(image_counts, image_counts.c.user_id == User.id)
        .outerjoin(spent_counts, spent_counts.c.user_id == User.id)
        .order_by(User.created_at.desc())
    )
    if query:
        statement = statement.where((User.email.contains(query)) | (User.display_name.contains(query)))
    if user_id:
        statement = statement.where(User.id == user_id)
    rows = db.execute(statement.offset(pagination.offset).limit(pagination.limit + 1)).all()
    items = [
        AdminUserCreditSummary(
            id=row.id,
            email=row.email,
            display_name=row.display_name,
            role=row.role,
            balance=int(row.balance),
            reserved_balance=int(row.reserved_balance),
            task_count=int(row.task_count),
            succeeded_image_count=int(row.succeeded_image_count),
            spent_credits=int(row.spent_credits),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows[: pagination.limit]
    ]
    return items, len(rows)


@router.get("/credits/me", response_model=ApiData[CreditOverviewRead])
def my_credits(user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[CreditOverviewRead]:
    account = ensure_credit_account(db, user.id)
    db.commit()
    db.refresh(account)
    return ApiData(
        data=CreditOverviewRead(
            account=account,
            recent_transactions=[],
        )
    )


@router.post("/credits/redeem", response_model=ApiData[CreditOverviewRead])
def redeem_my_activation_code(
    payload: CreditRedeemRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[CreditOverviewRead]:
    try:
        redeem_activation_code(db, user_id=user.id, code=payload.code)
    except ActivationCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return my_credits(user=user, db=db)


@router.get("/credits/usage", response_model=ApiData[list[CreditUsagePointRead]])
def my_credit_usage(
    days: int = Query(default=7),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[list[CreditUsagePointRead]]:
    if days not in {1, 7, 30}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只支持查看最近 1 天、7 天或 30 天")
    return ApiData(data=usage_points_for_user(db, user.id, days))


@router.get("/credits/transactions", response_model=ApiList[CreditTransactionRead])
def my_credit_transactions(
    transaction_filter: str = Query(default="all", alias="filter"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
) -> ApiList[CreditTransactionRead]:
    transactions, row_count = transaction_rows_for_user(
        db,
        user_id=user.id,
        pagination=pagination,
        transaction_filter=transaction_filter,
    )
    return ApiList(
        items=[CreditTransactionRead.model_validate(transaction) for transaction in transactions],
        page=build_page(pagination.limit, pagination.offset, row_count),
    )


@router.get("/admin/users", response_model=ApiList[AdminUserCreditSummary])
def list_admin_users(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
    query: str | None = Query(default=None, max_length=120),
) -> ApiList[AdminUserCreditSummary]:
    require_admin(user)
    items, row_count = user_summary_rows(db, pagination=pagination, query=query)
    return ApiList(items=items, page=build_page(pagination.limit, pagination.offset, row_count))


@router.get("/admin/users/{target_user_id}", response_model=ApiData[AdminUserCreditDetail])
def get_admin_user_detail(
    target_user_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AdminUserCreditDetail]:
    require_admin(user)
    pagination = Pagination(limit=1, offset=0)
    items, _ = user_summary_rows(db, pagination=pagination, user_id=target_user_id)
    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return ApiData(
        data=AdminUserCreditDetail(
            user=items[0],
            recent_transactions=[
                CreditTransactionRead.model_validate(transaction)
                for transaction in recent_transactions_for_user(db, target_user_id, limit=30)
            ],
        )
    )


@router.post("/admin/users/{target_user_id}/credits/adjust", response_model=ApiData[AdminUserCreditDetail])
def adjust_admin_user_credits(
    target_user_id: str,
    payload: AdminCreditAdjustmentRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[AdminUserCreditDetail]:
    require_admin(user)
    if not db.get(User, target_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    try:
        adjust_user_credits_by_admin(
            db,
            user_id=target_user_id,
            admin_user_id=user.id,
            amount=payload.amount,
            note=payload.note,
        )
    except CreditError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return get_admin_user_detail(target_user_id=target_user_id, user=user, db=db)


@router.post("/admin/activation-codes", response_model=ApiData[list[ActivationCodeCreatedRead]])
def create_admin_activation_codes(
    payload: ActivationCodeCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[list[ActivationCodeCreatedRead]]:
    require_admin(user)
    codes = create_activation_codes(
        db,
        admin_user_id=user.id,
        credit_amount=payload.credit_amount,
        count=payload.count,
        expires_at=payload.expires_at,
        note=payload.note,
    )
    db.commit()
    return ApiData(
        data=[
            ActivationCodeCreatedRead(
                id=code.id,
                code=plaintext,
                credit_amount=code.credit_amount,
                expires_at=code.expires_at,
                note=code.note,
            )
            for code, plaintext in codes
        ]
    )


@router.get("/admin/activation-codes", response_model=ApiList[ActivationCodeRead])
def list_admin_activation_codes(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(get_pagination),
) -> ApiList[ActivationCodeRead]:
    require_admin(user)
    codes = db.scalars(
        select(CreditActivationCode)
        .order_by(CreditActivationCode.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit + 1)
    ).all()
    return ApiList(
        items=[ActivationCodeRead.model_validate(code) for code in codes[: pagination.limit]],
        page=build_page(pagination.limit, pagination.offset, len(codes)),
    )
