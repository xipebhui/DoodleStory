from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import User
from app.services.security import get_current_user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    return get_current_user(request, db)
