import asyncio
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import (
    FileAsset,
    GeneratedImage,
    GenerationTask,
    Style,
    TaskCharacter,
    TaskCharacterAppearance,
    TaskPanel,
    TaskStyleReferenceImage,
    User,
)
from app.models.enums import (
    FileAssetPurpose,
    GeneratedImageJobKind,
    GeneratedImageSourceType,
    GeneratedImageStatus,
    GenerationStepName,
    ImageCountMode,
    StorageBackend,
    StyleReferenceMode,
    StyleStatus,
    TaskStatus,
    WorkflowStatus,
)
from app.services.image_generation import GeneratedImageFile
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

    def create_running_character_reference_task(self) -> tuple[str, str, str]:
        db = self.Session()
        user = User(email="owner-character@example.com", password_hash="hash")
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
            display_title="人物参考中断任务",
            original_text="故事正文",
            image_count_mode=ImageCountMode.auto,
            use_character_references=True,
            style_id=style.id,
            style_name_snapshot=style.name,
            style_prompt_snapshot=style.style_prompt,
            image_model_name_snapshot=style.image_model_name,
            style_aspect_ratio_snapshot=style.aspect_ratio,
            status=TaskStatus.running,
            current_step=GenerationStepName.generate_character_references,
            error_code="WorkerInterrupted",
            error_message="旧错误",
        )
        character = TaskCharacter(
            task=task,
            character_key="character_1",
            name="女主",
            description="主要人物",
        )
        appearance = TaskCharacterAppearance(
            character=character,
            appearance_key="character_1_adult",
            age_stage="成年",
            visual_prompt="成年女性，黑色长发，白色上衣",
            status=WorkflowStatus.queued,
        )
        db.add_all([task, character, appearance])
        db.commit()
        task_id = task.id
        appearance_id = appearance.id
        user_id = user.id
        db.close()
        return task_id, appearance_id, user_id

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

    def test_recover_character_references_without_active_jobs_requeues_task(self) -> None:
        task_id, _, _ = self.create_running_character_reference_task()
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

    def test_recover_character_references_with_active_jobs_keeps_task_running(self) -> None:
        task_id, appearance_id, user_id = self.create_running_character_reference_task()
        db = self.Session()
        db.add(
            GeneratedImage(
                task_id=task_id,
                panel_id=None,
                character_appearance_id=appearance_id,
                owner_user_id=user_id,
                job_kind=GeneratedImageJobKind.character_reference,
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

    def test_character_reference_image_job_passes_style_reference_snapshot_to_provider(self) -> None:
        db = self.Session()
        user = User(email="owner-style-reference@example.com", password_hash="hash")
        style = Style(
            name="极简黑白图片参考",
            status=StyleStatus.active,
            style_reference_mode=StyleReferenceMode.image,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_prompt="极简黑白",
        )
        style_asset = FileAsset(
            purpose=FileAssetPurpose.style_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="style_reference/minimal.png",
            public_url="https://cdn.example.com/style_reference/minimal.png",
            content_type="image/png",
            byte_size=10,
        )
        db.add_all([user, style, style_asset])
        db.flush()
        task = GenerationTask(
            owner_user_id=user.id,
            display_title="人物参考图任务",
            original_text="故事正文",
            image_count_mode=ImageCountMode.auto,
            use_character_references=True,
            style_id=style.id,
            style_name_snapshot=style.name,
            style_prompt_snapshot=style.style_prompt,
            image_model_name_snapshot=style.image_model_name,
            style_aspect_ratio_snapshot=style.aspect_ratio,
            style_reference_mode_snapshot=StyleReferenceMode.image,
            status=TaskStatus.running,
            current_step=GenerationStepName.generate_character_references,
        )
        task.style_reference_images.append(TaskStyleReferenceImage(asset=style_asset, reference_order=1))
        character = TaskCharacter(
            task=task,
            character_key="character_1",
            name="三叔",
            description="主要人物",
        )
        appearance = TaskCharacterAppearance(
            character=character,
            appearance_key="character_1_adult",
            age_stage="中年",
            visual_prompt="中年男性，黑色短发，神情严肃，穿深色夹克。",
            status=WorkflowStatus.queued,
        )
        image = GeneratedImage(
            task=task,
            panel_id=None,
            character_appearance=appearance,
            owner_user_id=user.id,
            job_kind=GeneratedImageJobKind.character_reference,
            status=GeneratedImageStatus.running,
            attempts=1,
            locked_by="worker-1",
            generation_number=1,
            source_type=GeneratedImageSourceType.initial,
            image_model_name_snapshot="gpt-image-2",
            final_prompt="旧版人物参考图 prompt",
        )
        db.add_all([task, character, appearance, image])
        db.commit()
        image_id = image.id
        db.close()

        generated = GeneratedImageFile(
            storage_backend=StorageBackend.qiniu,
            storage_key="generated_image/character.png",
            byte_size=123,
            checksum_sha256="hash",
            content_type="image/png",
            original_filename="character.png",
            provider_request_id="provider-request",
            public_url="https://cdn.example.com/generated_image/character.png",
        )
        with patch("app.services.task_worker.SessionLocal", self.Session), patch(
            "app.services.task_worker.reserve_image_credit"
        ), patch("app.services.task_worker.charge_reserved_image_credit"), patch(
            "app.services.task_worker.generate_xg_image", return_value=generated
        ) as generate:
            task_worker.process_character_reference_image_job(image_id)

        generate.assert_called_once()
        call_kwargs = generate.call_args.kwargs
        self.assertEqual(["https://cdn.example.com/style_reference/minimal.png"], [ref.url for ref in call_kwargs["references"]])
        self.assertIn("风格参考（参考图1）", call_kwargs["prompt"])
        self.assertNotIn("旧版人物参考图 prompt", call_kwargs["prompt"])

        db = self.Session()
        refreshed = db.scalar(select(GeneratedImage).where(GeneratedImage.id == image_id))
        self.assertIsNotNone(refreshed)
        self.assertEqual(GeneratedImageStatus.succeeded, refreshed.status)
        self.assertIn("风格参考（参考图1）", refreshed.final_prompt)
        db.close()


if __name__ == "__main__":
    unittest.main()
