import asyncio
from contextlib import contextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentConversation,
    AgentMessage,
    AgentRun,
    AgentStep,
    FileAsset,
    GeneratedImage,
    GenerationTask,
    Style,
    TaskPanel,
    User,
)
from app.models.enums import (
    AgentMessageRole,
    AgentRunStatus,
    AgentStepType,
    FileAssetPurpose,
    GeneratedImageStatus,
    StorageBackend,
    StyleStatus,
)
from app.schemas.agent import ComicPlan
from app.services import agent_runner, task_worker
from app.services.agent_comic_creation import (
    checkpoint_image_tool_results,
    create_comic_task_and_image_tools,
)
from app.services.credits import grant_initial_credits


def comic_plan() -> ComicPlan:
    return ComicPlan.model_validate(
        {
            "title": "深夜便利店的另一个我",
            "summary": "疲惫的上班族在便利店遇见未来的自己。",
            "panels": [
                {
                    "panel_key": "panel-1",
                    "story_beat": "加班者推开便利店门，看见一个熟悉背影。",
                    "visual_goal": "建立深夜疲惫和悬念。",
                    "image_prompt": "三比四竖幅水彩漫画，深夜便利店，加班者推门看向熟悉背影，冷暖灯光对比。",
                    "required_text": [],
                },
                {
                    "panel_key": "panel-2",
                    "story_beat": "背影转身，原来是十年后神情从容的自己。",
                    "visual_goal": "紧接上一格完成揭示。",
                    "image_prompt": "三比四竖幅水彩漫画，同一便利店同一机位，背影转身露出年长十岁的同一张脸。",
                    "required_text": ["别怕，你会走出来。"],
                },
            ],
        }
    )


class AgentComicCreationTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        with self.Session() as db:
            user = User(email="comic-agent@example.com", password_hash="hash")
            style = Style(
                name="清透水彩",
                status=StyleStatus.active,
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
                style_prompt="清透水彩、克制线条",
            )
            db.add_all([user, style])
            db.flush()
            conversation = AgentConversation(owner=user, title="漫画测试")
            message = AgentMessage(
                conversation=conversation,
                turn_id="turn-1",
                role=AgentMessageRole.user,
                content="一个加班者在便利店遇见十年后的自己",
                resource_refs_json=json.dumps(
                    [{"kind": "style", "id": style.id, "display_name": style.name}],
                    ensure_ascii=False,
                ),
                sequence=1,
            )
            run = AgentRun(conversation=conversation, turn_id="turn-1")
            db.add_all([conversation, message, run])
            db.commit()
            self.user_id = user.id
            self.style_id = style.id
            self.message_id = message.id
            self.run_id = run.id

    def create_task(self) -> str:
        with self.Session() as db:
            run = db.get(AgentRun, self.run_id)
            message = db.get(AgentMessage, self.message_id)
            style = db.get(Style, self.style_id)
            task = create_comic_task_and_image_tools(
                db=db,
                run=run,
                user_message=message,
                style=style,
                plan=comic_plan(),
            )
            return task.id

    def test_comic_plan_requires_exact_ordered_two_panels(self) -> None:
        payload = comic_plan().model_dump()
        payload["panels"][1]["panel_key"] = "panel-1"
        with self.assertRaises(ValidationError):
            ComicPlan.model_validate(payload)

    def test_task_creation_is_atomic_idempotent_and_keeps_agent_prompt_boundary(self) -> None:
        task_id = self.create_task()
        repeated_task_id = self.create_task()

        with self.Session() as db:
            task = db.get(GenerationTask, task_id)
            panels = db.scalars(
                select(TaskPanel).where(TaskPanel.task_id == task_id).order_by(TaskPanel.panel_order)
            ).all()
            images = db.scalars(
                select(GeneratedImage).where(GeneratedImage.task_id == task_id).order_by(GeneratedImage.created_at)
            ).all()
            tool_calls = db.scalars(
                select(AgentStep).where(
                    AgentStep.run_id == self.run_id,
                    AgentStep.step_type == AgentStepType.tool_call,
                )
            ).all()

        self.assertEqual(task_id, repeated_task_id)
        self.assertEqual(2, len(panels))
        self.assertEqual(2, len(images))
        self.assertEqual(2, len(tool_calls))
        self.assertEqual(2, task.requested_image_count)
        self.assertEqual([panel.generated_prompt for panel in panels], [image.final_prompt for image in images])
        self.assertTrue(all("清透水彩、克制线条" not in (image.final_prompt or "") for image in images))
        self.assertEqual(2, len({step.idempotency_key for step in tool_calls}))

    def test_tool_results_checkpoint_once_after_both_jobs_finish(self) -> None:
        task_id = self.create_task()
        with self.Session() as db:
            run = db.get(AgentRun, self.run_id)
            self.assertIsNone(checkpoint_image_tool_results(db, run))
            images = db.scalars(
                select(GeneratedImage).where(GeneratedImage.task_id == task_id).order_by(GeneratedImage.created_at)
            ).all()
            asset = FileAsset(
                purpose=FileAssetPurpose.generated_image,
                storage_backend=StorageBackend.local,
                storage_key="agent-test/panel-1.png",
                content_type="image/png",
                byte_size=100,
                width=768,
                height=1024,
            )
            db.add(asset)
            db.flush()
            images[0].status = GeneratedImageStatus.succeeded
            images[0].asset_id = asset.id
            images[1].status = GeneratedImageStatus.failed
            images[1].error_code = "ProviderFailed"
            images[1].error_message = "图片 Provider 返回失败"
            db.commit()

            outputs = checkpoint_image_tool_results(db, run)
            repeated = checkpoint_image_tool_results(db, run)
            result_count = db.scalar(
                select(func.count(AgentStep.id)).where(
                    AgentStep.run_id == self.run_id,
                    AgentStep.step_type == AgentStepType.tool_result,
                )
            )
            db.refresh(run)

        self.assertEqual(outputs, repeated)
        self.assertEqual(["succeeded", "failed"], [item["status"] for item in outputs])
        self.assertEqual(2, result_count)
        self.assertEqual(AgentRunStatus.running, run.status)

    def test_insufficient_credit_fails_image_job_without_calling_provider(self) -> None:
        task_id = self.create_task()
        with self.Session() as db:
            user = db.get(User, self.user_id)
            grant_initial_credits(db, user, amount=0)
            image = db.scalar(
                select(GeneratedImage)
                .where(GeneratedImage.task_id == task_id)
                .order_by(GeneratedImage.created_at)
                .limit(1)
            )
            image.status = GeneratedImageStatus.running
            image.attempts = 1
            image.locked_by = "agent-test-worker"
            db.commit()
            image_id = image.id

        with (
            patch("app.services.task_worker.SessionLocal", self.Session),
            patch("app.services.task_worker.get_settings", return_value=SimpleNamespace()),
            patch("app.services.task_worker.generate_panel_image_request") as provider,
        ):
            task_worker.process_initial_panel_image_job(image_id)

        provider.assert_not_called()
        with self.Session() as db:
            image = db.get(GeneratedImage, image_id)
            self.assertEqual(GeneratedImageStatus.failed, image.status)
            self.assertEqual("InsufficientCreditsError", image.error_code)

    def test_tool_call_wait_and_result_spans_keep_stable_database_ids(self) -> None:
        recorded: list[tuple[str, dict[str, object]]] = []

        class FakeSpan:
            def __init__(self, attributes):
                self.attributes = attributes

            def set_attribute(self, key, value):
                self.attributes[key] = value

        @contextmanager
        def record_span(name, *, attributes, **kwargs):
            copied = dict(attributes)
            recorded.append((name, copied))
            yield FakeSpan(copied)

        with (
            patch("app.services.agent_comic_creation.agent_span", side_effect=record_span),
            patch("app.services.agent_runner.agent_span", side_effect=record_span),
            patch("app.services.agent_runner.database.SessionLocal", self.Session),
        ):
            task_id = self.create_task()
            with self.Session() as db:
                images = db.scalars(
                    select(GeneratedImage).where(GeneratedImage.task_id == task_id)
                ).all()
                for image in images:
                    image.status = GeneratedImageStatus.failed
                    image.error_code = "InjectedImageFailure"
                db.commit()
            outputs = asyncio.run(agent_runner._wait_for_image_tools(self.run_id))

        self.assertEqual(["failed", "failed"], [output["status"] for output in outputs])
        names = [name for name, _ in recorded]
        self.assertEqual(2, names.count("agent.tool_call"))
        self.assertEqual(1, names.count("agent.tool_wait"))
        self.assertEqual(2, names.count("agent.tool_result"))
        for name, attributes in recorded:
            if name in {"agent.tool_call", "agent.tool_result"}:
                self.assertTrue(attributes["agent_step_id"])
                self.assertTrue(attributes["task_id"])
                self.assertTrue(attributes["panel_id"])
                self.assertTrue(attributes["image_job_id"])
                self.assertNotIn("agent:", str(attributes["idempotency_digest"]))


if __name__ == "__main__":
    unittest.main()
