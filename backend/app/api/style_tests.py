from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import StyleTest, User
from app.schemas.common import ApiData
from app.schemas.style import StyleTestRead

router = APIRouter(prefix="/style-tests", tags=["style-tests"])


@router.get("/{style_test_id}", response_model=ApiData[StyleTestRead])
def get_style_test(
    style_test_id: str,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApiData[StyleTestRead]:
    style_test = db.scalar(
        select(StyleTest)
        .where(StyleTest.id == style_test_id)
        .options(selectinload(StyleTest.output_asset))
    )
    if not style_test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格测试不存在")

    return ApiData(data=StyleTestRead.model_validate(style_test))
