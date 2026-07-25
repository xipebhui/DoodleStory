import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentConversation,
    AgentEvent,
    AgentRun,
    FileAsset,
    GeneratedImage,
    GenerationTask,
    Style,
    TaskPanel,
    User,
    new_id,
)
from app.models.enums import (
    AgentEventType,
    AgentRunStatus,
    FileAssetPurpose,
    GeneratedImageStatus,
    ImageCountMode,
    StorageBackend,
    StoryInputMode,
    StyleStatus,
    TaskStatus,
)
from app.schemas.agent import AgentPanelRegenerationCreate
from app.api.agent_conversations import pause_agent_run, resume_agent_run
from app.services.agent_panel_versions import (
    AgentPanelVersionError,
    accept_image_version,
    process_panel_revision_run,
    restore_image_version,
    start_panel_regeneration,
)
from app.services.agent_runner import enqueue_agent_run_from_thread
from app.services.agent_tool_runtime import (
    GenericToolExecutor,
    build_runtime_context,
    create_default_tool_registry,
)
from app.services.agent_vision import InspectionIssue, InspectionResult
from app.services.task_worker import panel_edit_requests_text_change


class AgentPanelVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        with self.Session() as db:
            owner = User(email=f"panel-{new_id()}@example.com", password_hash="hash")
            other = User(email=f"other-{new_id()}@example.com", password_hash="hash")
            style = Style(
                name="Panel version style",
                status=StyleStatus.active,
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
                style_prompt="固定风格",
            )
            db.add_all([owner, other, style])
            db.flush()
            task = GenerationTask(
                owner_user_id=owner.id,
                display_title="局部版本测试",
                original_text="两个连续场景",
                story_input_mode=StoryInputMode.adapted,
                image_count_mode=ImageCountMode.fixed,
                requested_image_count=2,
                style_id=style.id,
                style_name_snapshot=style.name,
                style_prompt_snapshot=style.style_prompt,
                image_model_name_snapshot=style.image_model_name,
                style_aspect_ratio_snapshot=style.aspect_ratio,
                status=TaskStatus.succeeded,
            )
            db.add(task)
            db.flush()
            panel_one = TaskPanel(
                task_id=task.id,
                panel_order=1,
                original_text_segment="主角在雨里",
                generated_prompt="主角在雨里，蓝色外套",
            )
            panel_two = TaskPanel(
                task_id=task.id,
                panel_order=2,
                original_text_segment="主角走进车站",
                generated_prompt="主角走进车站，蓝色外套",
            )
            conversation = AgentConversation(owner=owner, title="局部版本")
            db.add_all([panel_one, panel_two, conversation])
            db.flush()
            run = AgentRun(
                conversation=conversation,
                task_id=task.id,
                turn_id=new_id(),
                status=AgentRunStatus.succeeded,
            )
            db.add(run)
            asset_one = self._asset(db, "panel-one-v1")
            asset_two = self._asset(db, "panel-two-v1")
            image_one = GeneratedImage(
                task_id=task.id,
                panel_id=panel_one.id,
                owner_user_id=owner.id,
                status=GeneratedImageStatus.succeeded,
                generation_number=1,
                is_current=True,
                image_prompt=panel_one.generated_prompt,
                final_prompt=panel_one.generated_prompt,
                image_model_name_snapshot=style.image_model_name,
                asset_id=asset_one.id,
            )
            image_two = GeneratedImage(
                task_id=task.id,
                panel_id=panel_two.id,
                owner_user_id=owner.id,
                status=GeneratedImageStatus.succeeded,
                generation_number=1,
                is_current=True,
                image_prompt=panel_two.generated_prompt,
                final_prompt=panel_two.generated_prompt,
                image_model_name_snapshot=style.image_model_name,
                asset_id=asset_two.id,
            )
            db.add_all([image_one, image_two])
            db.commit()
            self.owner_id = owner.id
            self.other_id = other.id
            self.conversation_id = conversation.id
            self.task_id = task.id
            self.panel_one_id = panel_one.id
            self.panel_two_id = panel_two.id
            self.image_one_id = image_one.id
            self.image_two_id = image_two.id

    @staticmethod
    def _asset(db, suffix: str) -> FileAsset:
        asset = FileAsset(
            purpose=FileAssetPurpose.generated_image,
            storage_backend=StorageBackend.local,
            storage_key=f"agent-panel-tests/{suffix}-{new_id()}.png",
            content_type="image/png",
            byte_size=100,
            width=768,
            height=1024,
        )
        db.add(asset)
        db.flush()
        return asset

    def _start_regeneration(self, db, *, allow_auto_revision: bool = False) -> AgentRun:
        return start_panel_regeneration(
            db,
            conversation_id=self.conversation_id,
            task_id=self.task_id,
            panel_id=self.panel_one_id,
            payload=AgentPanelRegenerationCreate(
                instruction="表情更紧张，衣服和场景不变",
                source_image_version_id=self.image_one_id,
                expected_credit_cost=1,
                allow_auto_revision=allow_auto_revision,
            ),
            owner_user_id=self.owner_id,
        )

    def test_accept_restore_are_idempotent_and_enforce_full_ownership_chain(self) -> None:
        with self.Session() as db:
            accepted = accept_image_version(
                db,
                conversation_id=self.conversation_id,
                task_id=self.task_id,
                panel_id=self.panel_one_id,
                image_id=self.image_one_id,
                owner_user_id=self.owner_id,
            )
            accepted_at = accepted.accepted_at
            repeated = accept_image_version(
                db,
                conversation_id=self.conversation_id,
                task_id=self.task_id,
                panel_id=self.panel_one_id,
                image_id=self.image_one_id,
                owner_user_id=self.owner_id,
            )
            self.assertEqual(accepted_at, repeated.accepted_at)
            with self.assertRaises(AgentPanelVersionError):
                accept_image_version(
                    db,
                    conversation_id=self.conversation_id,
                    task_id=self.task_id,
                    panel_id=self.panel_two_id,
                    image_id=self.image_one_id,
                    owner_user_id=self.owner_id,
                )
            with self.assertRaises(AgentPanelVersionError):
                restore_image_version(
                    db,
                    conversation_id=self.conversation_id,
                    task_id=self.task_id,
                    panel_id=self.panel_one_id,
                    image_id=self.image_one_id,
                    owner_user_id=self.other_id,
                )

            newer_asset = self._asset(db, "panel-one-v2")
            newer = GeneratedImage(
                task_id=self.task_id,
                panel_id=self.panel_one_id,
                owner_user_id=self.owner_id,
                status=GeneratedImageStatus.succeeded,
                generation_number=2,
                is_current=True,
                image_model_name_snapshot="gpt-image-2",
                asset_id=newer_asset.id,
            )
            repeated.is_current = False
            db.add(newer)
            db.commit()
            restored = restore_image_version(
                db,
                conversation_id=self.conversation_id,
                task_id=self.task_id,
                panel_id=self.panel_one_id,
                image_id=self.image_one_id,
                owner_user_id=self.owner_id,
            )
            self.assertTrue(restored.is_current)
            self.assertFalse(db.get(GeneratedImage, newer.id).is_current)
            self.assertTrue(db.get(GeneratedImage, self.image_two_id).is_current)

    def test_visual_only_instruction_keeps_text_boundary(self) -> None:
        self.assertFalse(
            panel_edit_requests_text_change(
                "让眉眼和握票动作更紧张，保持衣服、构图和场景不变"
            )
        )
        for instruction in (
            "删除旁白",
            "标题换成出发",
            "调整文字排版",
            "画面改成无字版本",
        ):
            with self.subTest(instruction=instruction):
                self.assertTrue(panel_edit_requests_text_change(instruction))

    def test_worker_notification_enqueues_without_waiting_for_agent_loop(self) -> None:
        loop = Mock()
        queue = Mock()
        with (
            patch("app.services.agent_runner._agent_queue_loop", loop),
            patch("app.services.agent_runner._agent_queue", queue),
        ):
            enqueue_agent_run_from_thread("run-1")

        loop.call_soon_threadsafe.assert_called_once_with(
            queue.put_nowait,
            "run-1",
        )

    def test_regeneration_tool_replay_creates_one_target_panel_version(self) -> None:
        with self.Session() as db:
            run = self._start_regeneration(db)
            created = db.scalar(
                select(GeneratedImage).where(
                    GeneratedImage.panel_id == self.panel_one_id,
                    GeneratedImage.generation_number == 2,
                )
            )
            self.assertIsNotNone(created)
            self.assertEqual("表情更紧张，衣服和场景不变", created.user_instruction)
            self.assertFalse(created.is_current)
            self.assertEqual(
                1,
                db.scalar(
                    select(func.count(GeneratedImage.id)).where(
                        GeneratedImage.panel_id == self.panel_two_id
                    )
                ),
            )
            executor = GenericToolExecutor(create_default_tool_registry())
            call = next(step for step in run.steps if step.idempotency_key and ":revision" in step.idempotency_key)
            payload = json.loads(call.input_ref)
            replay = executor.execute(
                db,
                run=run,
                tool_name="generate_image",
                arguments=payload["arguments"],
                idempotency_key=call.idempotency_key,
                context=build_runtime_context(db, run, image_budget_limit=2),
            )
            self.assertTrue(replay.replayed)
            self.assertEqual(
                2,
                db.scalar(
                    select(func.count(GeneratedImage.id)).where(
                        GeneratedImage.panel_id == self.panel_one_id
                    )
                ),
            )
            self.assertEqual(1, run.image_call_count)

    def _assert_vl_verdict(self, verdict: str, expected_state: str) -> None:
        with self.Session() as db:
            run = self._start_regeneration(db)
            image = db.scalar(
                select(GeneratedImage).where(
                    GeneratedImage.panel_id == self.panel_one_id,
                    GeneratedImage.generation_number == 2,
                )
            )
            asset_id = self._asset(db, f"verdict-{verdict}").id
            image.asset_id = asset_id
            image.status = GeneratedImageStatus.succeeded
            image.final_prompt = "修订后提示词"
            db.commit()
            result = InspectionResult(
                verdict=verdict,
                scores={
                    "story_alignment": 0.9,
                    "character_consistency": 0.9,
                    "continuity": 0.9,
                    "text_accuracy": 0.9,
                    "visual_artifacts": 0.9,
                },
                issues=[],
            )
            with patch(
                "app.services.agent_tool_runtime.inspect_generated_image",
                return_value=(result, "test-vl", "test-model", 12),
            ):
                outcome = process_panel_revision_run(db, run)
            self.assertEqual(expected_state, outcome.state)
            self.assertEqual(3, db.scalar(select(func.count(GeneratedImage.id))))

    def test_vl_accept_completes_without_unapproved_extra_image(self) -> None:
        self._assert_vl_verdict("accept", "completed")

    def test_vl_revise_waits_without_unapproved_extra_image(self) -> None:
        self._assert_vl_verdict("revise", "waiting_input")

    def test_vl_ask_user_waits_without_unapproved_extra_image(self) -> None:
        self._assert_vl_verdict("ask_user", "waiting_input")

    def test_vl_blocked_waits_without_unapproved_extra_image(self) -> None:
        self._assert_vl_verdict("blocked", "waiting_input")

    def test_authorized_auto_revision_is_capped_at_one_extra_version(self) -> None:
        with self.Session() as db:
            run = self._start_regeneration(db, allow_auto_revision=True)
            first = db.scalar(
                select(GeneratedImage).where(
                    GeneratedImage.panel_id == self.panel_one_id,
                    GeneratedImage.generation_number == 2,
                )
            )
            first_asset_id = self._asset(db, "auto-first").id
            first.asset_id = first_asset_id
            first.status = GeneratedImageStatus.succeeded
            first.final_prompt = "第一次修订"
            db.commit()
            revise = InspectionResult(
                verdict="revise",
                scores={
                    "story_alignment": 0.7,
                    "character_consistency": 0.8,
                    "continuity": 0.8,
                    "text_accuracy": 0.9,
                    "visual_artifacts": 0.7,
                },
                issues=[
                    InspectionIssue(
                        code="expression",
                        message="表情仍不够紧张",
                        suggested_change="加强眉眼和握拳动作，保持衣服与场景",
                    )
                ],
            )
            accepted = InspectionResult(
                verdict="accept",
                scores={
                    "story_alignment": 0.95,
                    "character_consistency": 0.95,
                    "continuity": 0.95,
                    "text_accuracy": 0.95,
                    "visual_artifacts": 0.95,
                },
            )
            with patch(
                "app.services.agent_tool_runtime.inspect_generated_image",
                side_effect=[
                    (revise, "test-vl", "test-model", 12),
                    (accepted, "test-vl", "test-model", 11),
                ],
            ):
                first_outcome = process_panel_revision_run(db, run)
                self.assertEqual("waiting_tool", first_outcome.state)
                automatic = db.scalar(
                    select(GeneratedImage).where(
                        GeneratedImage.panel_id == self.panel_one_id,
                        GeneratedImage.generation_number == 3,
                    )
                )
                automatic_asset_id = self._asset(db, "auto-second").id
                automatic.asset_id = automatic_asset_id
                automatic.status = GeneratedImageStatus.succeeded
                automatic.final_prompt = "自动修订"
                db.commit()
                second_outcome = process_panel_revision_run(db, run)
            self.assertEqual("completed", second_outcome.state)
            self.assertEqual(4, db.scalar(select(func.count(GeneratedImage.id))))
            self.assertEqual(2, run.image_call_count)

    def test_pause_resume_are_idempotent_owned_and_reject_terminal_runs(self) -> None:
        with self.Session() as db:
            owner = db.get(User, self.owner_id)
            other = db.get(User, self.other_id)
            conversation = db.get(AgentConversation, self.conversation_id)
            run = AgentRun(
                conversation=conversation,
                task_id=self.task_id,
                turn_id=new_id(),
                status=AgentRunStatus.waiting_for_tool,
            )
            db.add(run)
            db.commit()
            paused = pause_agent_run(run.id, user=owner, db=db).data
            repeated = pause_agent_run(run.id, user=owner, db=db).data
            self.assertEqual(AgentRunStatus.paused, paused.status)
            self.assertEqual(AgentRunStatus.paused, repeated.status)
            with patch(
                "app.api.agent_conversations.enqueue_agent_run",
                new_callable=AsyncMock,
            ) as enqueue:
                resumed = asyncio.run(
                    resume_agent_run(run.id, user=owner, db=db)
                ).data
            self.assertEqual(AgentRunStatus.queued, resumed.status)
            enqueue.assert_awaited_once_with(run.id)
            event_types = db.scalars(
                select(AgentEvent.event_type).where(AgentEvent.run_id == run.id)
            ).all()
            self.assertEqual(
                [AgentEventType.run_paused, AgentEventType.run_resumed],
                event_types,
            )
            with self.assertRaises(HTTPException) as wrong_owner:
                pause_agent_run(run.id, user=other, db=db)
            self.assertEqual(404, wrong_owner.exception.status_code)
            terminal = db.scalar(
                select(AgentRun).where(
                    AgentRun.conversation_id == self.conversation_id,
                    AgentRun.status == AgentRunStatus.succeeded,
                )
            )
            with self.assertRaises(HTTPException) as terminal_pause:
                pause_agent_run(terminal.id, user=owner, db=db)
            self.assertEqual(409, terminal_pause.exception.status_code)


if __name__ == "__main__":
    unittest.main()
