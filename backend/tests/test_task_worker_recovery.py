import asyncio
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import GeneratedImage, GenerationTask, Style, TaskPanel, User
from app.models.enums import (
    GeneratedImageSourceType,
    GeneratedImageStatus,
    GenerationStepName,
    ImageCountMode,
    StyleReferenceMode,
    StyleStatus,
    TaskStatus,
)
from app.services import task_worker


class TaskWorkerRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def create_running_generate_images_task(self) -> tuple[str, str, str]:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash")
        style = Style(
            name="测试风格",
            status=StyleStatus.active,
            style_reference_mode=StyleReferenceMode.prompt,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_prompt="手绘漫画风",
        )
        db.add_all([user, style])
        db.flush()
        task = GenerationTask(
            owner_user_id=user.id,
            display_title="中断任务",
            original_text="故事正文",
            image_count_mode=ImageCountMode.auto,
            style_id=style.id,
            style_name_snapshot=style.name,
            style_prompt_snapshot=style.style_prompt,
            image_model_name_snapshot=style.image_model_name,
            style_aspect_ratio_snapshot=style.aspect_ratio,
            status=TaskStatus.running,
            current_step=GenerationStepName.generate_images,
            error_code="WorkerInterrupted",
            error_message="旧错误",
        )
        panel = TaskPanel(panel_order=1, original_text_segment="第一幕")
        task.panels.append(panel)
        db.add(task)
        db.commit()
        task_id = task.id
        panel_id = panel.id
        user_id = user.id
        db.close()
        return task_id, panel_id, user_id

    def test_recover_generate_images_without_active_jobs_requeues_task(self) -> None:
        task_id, _, _ = self.create_running_generate_images_task()
        queue: asyncio.Queue[str] = asyncio.Queue()

        async def run_recover() -> None:
            with patch("app.services.task_worker.SessionLocal", self.Session):
                task_worker._queue = queue
                try:
                    await task_worker.recover_queued_tasks()
                finally:
                    task_worker._queue = None

        asyncio.run(run_recover())

        db = self.Session()
        task = db.scalar(select(GenerationTask).where(GenerationTask.id == task_id))
        self.assertIsNotNone(task)
        self.assertEqual(TaskStatus.queued, task.status)
        self.assertIsNone(task.error_code)
        self.assertEqual(task_id, queue.get_nowait())

    def test_recover_generate_images_with_active_jobs_keeps_task_running(self) -> None:
        task_id, panel_id, user_id = self.create_running_generate_images_task()
        db = self.Session()
        db.add(
            GeneratedImage(
                task_id=task_id,
                panel_id=panel_id,
                owner_user_id=user_id,
                status=GeneratedImageStatus.queued,
                generation_number=1,
                source_type=GeneratedImageSourceType.initial,
                image_model_name_snapshot="gpt-image-2",
            )
        )
        db.commit()
        db.close()
        queue: asyncio.Queue[str] = asyncio.Queue()

        async def run_recover() -> None:
            with patch("app.services.task_worker.SessionLocal", self.Session):
                task_worker._queue = queue
                try:
                    await task_worker.recover_queued_tasks()
                finally:
                    task_worker._queue = None

        asyncio.run(run_recover())

        db = self.Session()
        task = db.scalar(select(GenerationTask).where(GenerationTask.id == task_id))
        self.assertIsNotNone(task)
        self.assertEqual(TaskStatus.running, task.status)
        self.assertTrue(queue.empty())


if __name__ == "__main__":
    unittest.main()
