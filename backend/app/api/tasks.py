from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import GenerationTask, Style, User
from app.models.enums import UserRole
from app.schemas.common import ApiData
from app.schemas.task import TaskCreate, TaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


def task_access_filter(user: User):
    if user.role == UserRole.admin:
        return True
    return GenerationTask.owner_user_id == user.id


@router.get("", response_model=ApiData[list[TaskRead]])
def list_tasks(user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[list[TaskRead]]:
    statement = select(GenerationTask).options(selectinload(GenerationTask.panels)).order_by(GenerationTask.created_at.desc())
    if user.role != UserRole.admin:
        statement = statement.where(GenerationTask.owner_user_id == user.id)

    tasks = db.scalars(statement).all()
    return ApiData(data=[TaskRead.model_validate(task) for task in tasks])


@router.post("", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
def create_task(payload: TaskCreate, _: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    style = db.scalar(select(Style).where(Style.id == payload.style_id))
    if not style:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格不存在")

    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="图片生成 Provider 尚未接入，暂不允许创建生成任务")


@router.get("/{task_id}", response_model=ApiData[TaskRead])
def get_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ApiData[TaskRead]:
    task = db.scalar(
        select(GenerationTask)
        .where(GenerationTask.id == task_id)
        .options(selectinload(GenerationTask.panels))
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if user.role != UserRole.admin and task.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该任务")

    return ApiData(data=TaskRead.model_validate(task))
