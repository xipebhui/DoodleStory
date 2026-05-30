import base64
import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import User
from app.models.enums import UserRole

SESSION_COOKIE = "doodlestory_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 14


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, encoded_salt, encoded_digest = password_hash.split("$", 2)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    salt = base64.urlsafe_b64decode(encoded_salt.encode())
    expected = base64.urlsafe_b64decode(encoded_digest.encode())
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390_000)
    return hmac.compare_digest(actual, expected)


def create_session_token(user_id: str) -> str:
    settings = get_settings()
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{user_id}.{expires_at}"
    signature = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def parse_session_token(token: str) -> str | None:
    settings = get_settings()
    try:
        user_id, expires_at, signature = token.split(".", 2)
        payload = f"{user_id}.{expires_at}"
    except ValueError:
        return None

    expected = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    if int(expires_at) < int(time.time()):
        return None

    return user_id


def set_session_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user_id),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=SESSION_TTL_SECONDS,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


def user_role_for_email(email: str) -> UserRole:
    return UserRole.admin if email.lower() in get_settings().admin_email_set else UserRole.user


def get_current_user(request: Request, db: Session) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = parse_session_token(token) if token else None

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")

    return user
