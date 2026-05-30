from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import User
from app.schemas.common import ApiData
from app.schemas.auth import LoginRequest, RegisterRequest, SessionRead, UserRead
from app.services.security import clear_session_cookie, hash_password, set_session_cookie, user_role_for_email, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=ApiData[SessionRead])
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> ApiData[SessionRead]:
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")

    user = User(
        email=email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=user_role_for_email(email),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, user.id)
    return ApiData(data=SessionRead(user=UserRead.model_validate(user)))


@router.post("/login", response_model=ApiData[SessionRead])
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> ApiData[SessionRead]:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")

    set_session_cookie(response, user.id)
    return ApiData(data=SessionRead(user=UserRead.model_validate(user)))


@router.post("/logout", response_model=ApiData[dict[str, bool]])
def logout(response: Response) -> ApiData[dict[str, bool]]:
    clear_session_cookie(response)
    return ApiData(data={"ok": True})


@router.get("/me", response_model=ApiData[SessionRead])
def me(user: User = Depends(current_user)) -> ApiData[SessionRead]:
    return ApiData(data=SessionRead(user=UserRead.model_validate(user)))
