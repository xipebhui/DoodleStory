import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    DurableAgentArtifact,
    DurableAgentTask,
    NativeAgentArtifact,
    NativeAgentConversation,
    NativeAgentRun,
    User,
)
from app.models.enums import AgentRunStatus, AgentSkillStatus
from app.schemas.native_agent import NativeAgentFollowUpCreate
from app.services.durable_agent_runtime import initialize_workflow, workflow_for_native_run
from app.services.native_agent_follow_up import (
    NativeAgentFollowUpError,
    create_follow_up_run,
)
from app.services.native_agent_loop import native_agent_instructions
from app.services import native_agent_worker


class NativeAgentFollowUpTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record) -> None:
            del record
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        self.user = User(email="follow-up@example.com", password_hash="hash")
        self.db.add(self.user)
        self.db.flush()
        self.skill = AgentSkill(
            slug="follow-up-article",
            name="Follow-up 文案团队",
            description="test",
            draft_instructions="严格执行本轮目标",
            draft_tool_names_json=(
                '["write_article","review_article","submit_final_article"]'
            ),
            draft_revision=1,
            status=AgentSkillStatus.published,
        )
        self.db.add(self.skill)
        self.db.flush()
        self.version = AgentSkillVersion(
            skill_id=self.skill.id,
            version=1,
            name_snapshot=self.skill.name,
            description_snapshot=self.skill.description,
            instructions=self.skill.draft_instructions,
            tool_names_json=self.skill.draft_tool_names_json,
            content_hash="sha256:skill",
        )
        self.db.add(self.version)
        self.db.flush()
        self.skill.active_version_id = self.version.id
        self.conversation = NativeAgentConversation(
            owner_user_id=self.user.id,
            title="Follow-up test",
        )
        self.db.add(self.conversation)
        self.db.flush()
        self.parent = NativeAgentRun(
            conversation_id=self.conversation.id,
            skill_version_id=self.version.id,
            status=AgentRunStatus.succeeded,
            model_snapshot="test-model",
            model_route_snapshot="huomiao_responses",
            model_provider_snapshot="huomiao",
            model_api_shape_snapshot="responses",
            skill_name_snapshot=self.version.name_snapshot,
            skill_version_snapshot=self.version.version,
            skill_content_hash_snapshot=self.version.content_hash,
            style_name_snapshot="纸片风",
            style_prompt_snapshot="纸片拼贴",
            image_model_snapshot="image-model",
            aspect_ratio_snapshot="9:16",
            style_reference_urls_json='["https://example.com/ref.png"]',
            creation_channel_context_json='{"audience":"创作者"}',
            youtube_publish_confirmation_json='{"confirmed":true}',
            final_output="父 Run 的最终正文",
        )
        self.db.add(self.parent)
        self.db.flush()
        self.parent_workflow = initialize_workflow(
            self.db,
            native_run=self.parent,
            include_article_tasks=True,
        )
        research_task = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == self.parent_workflow.id,
                DurableAgentTask.task_key == "research_topics",
            )
        )
        self.db.add(
            DurableAgentArtifact(
                workflow_id=self.parent_workflow.id,
                task_id=research_task.id,
                artifact_key="topic_candidates",
                artifact_type="topic_candidates",
                version=1,
                status="committed",
                content_json='{"candidates":[{"title":"原选题"}]}',
                content_hash="sha256:artifact",
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def _payload(
        self,
        *,
        content: str = "把正文压缩到 200 字以内",
        key: str = "follow-up-key-001",
    ) -> NativeAgentFollowUpCreate:
        return NativeAgentFollowUpCreate(content=content, idempotency_key=key)

    def test_create_follow_up_freezes_parent_context_and_isolates_workflow(self) -> None:
        self.db.add_all(
            [
                NativeAgentArtifact(
                    run_id=self.parent.id,
                    artifact_type="article_draft",
                    schema_version=1,
                    version=1,
                    status="approved",
                    producer_role="writer",
                    content_json='{"body_markdown":"已批准正文"}',
                    content_hash="sha256:approved-native",
                ),
                NativeAgentArtifact(
                    run_id=self.parent.id,
                    artifact_type="article_review",
                    schema_version=1,
                    version=1,
                    status="rejected",
                    producer_role="reviewer",
                    content_json='{"summary":"已拒绝内容"}',
                    content_hash="sha256:rejected-native",
                ),
            ]
        )
        self.db.commit()
        checkpoint_id = self.parent_workflow.current_checkpoint_id
        child, replayed = create_follow_up_run(
            self.db,
            parent_run=self.parent,
            user=self.user,
            payload=self._payload(),
        )
        self.db.commit()

        self.assertFalse(replayed)
        self.assertEqual(self.parent.id, child.parent_run_id)
        self.assertEqual(checkpoint_id, child.continued_from_checkpoint_id)
        self.assertEqual(self.parent.skill_version_id, child.skill_version_id)
        self.assertEqual(self.parent.model_snapshot, child.model_snapshot)
        self.assertEqual(
            self.parent.model_route_snapshot,
            child.model_route_snapshot,
        )
        self.assertEqual(
            self.parent.model_provider_snapshot,
            child.model_provider_snapshot,
        )
        self.assertEqual(
            self.parent.model_api_shape_snapshot,
            child.model_api_shape_snapshot,
        )
        self.assertEqual(self.parent.style_prompt_snapshot, child.style_prompt_snapshot)
        self.assertIsNone(child.youtube_publish_confirmation_json)
        self.assertIsNone(child.youtube_publish_confirmed_at)
        context = json.loads(child.continuation_context_json)
        self.assertEqual(self.parent.id, context["source_run"]["id"])
        self.assertEqual("父 Run 的最终正文", context["source_run"]["final_output"])
        self.assertEqual(
            "sha256:artifact",
            context["durable_artifacts"][0]["content_hash"],
        )
        self.assertEqual(1, len(context["native_artifacts"]))
        self.assertEqual(
            "sha256:approved-native",
            context["native_artifacts"][0]["content_hash"],
        )
        self.assertNotIn("已拒绝内容", child.continuation_context_json)
        child_workflow = workflow_for_native_run(self.db, child.id)
        self.assertIsNotNone(child_workflow)
        self.assertNotEqual(self.parent_workflow.id, child_workflow.id)
        child_tasks = self.db.scalars(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == child_workflow.id
            )
        ).all()
        self.assertEqual(6, len(child_tasks))
        self.assertEqual(AgentRunStatus.succeeded, self.parent.status)

        instructions = native_agent_instructions(child)
        self.assertIn("<follow_up_context>", instructions)
        self.assertIn("父 Run 的最终正文", instructions)
        self.assertIn("当前用户输入是本轮唯一的新目标", instructions)
        self.assertNotIn("<youtube_publish_context>", instructions)

    def test_same_idempotency_request_replays_and_changed_payload_conflicts(self) -> None:
        child, replayed = create_follow_up_run(
            self.db,
            parent_run=self.parent,
            user=self.user,
            payload=self._payload(),
        )
        self.db.commit()
        replay, replayed = create_follow_up_run(
            self.db,
            parent_run=self.parent,
            user=self.user,
            payload=self._payload(),
        )
        self.assertTrue(replayed)
        self.assertEqual(child.id, replay.id)

        with self.assertRaisesRegex(
            NativeAgentFollowUpError,
            "幂等键已用于不同",
        ):
            create_follow_up_run(
                self.db,
                parent_run=self.parent,
                user=self.user,
                payload=self._payload(content="改成另一项任务"),
            )

    def test_rejects_unsuccessful_parent_and_foreign_owner(self) -> None:
        self.parent.status = AgentRunStatus.failed
        with self.assertRaisesRegex(NativeAgentFollowUpError, "只有已成功"):
            create_follow_up_run(
                self.db,
                parent_run=self.parent,
                user=self.user,
                payload=self._payload(),
            )
        self.db.rollback()

        other = User(email="other@example.com", password_hash="hash")
        self.db.add(other)
        self.db.commit()
        with self.assertRaisesRegex(NativeAgentFollowUpError, "不存在或不可访问"):
            create_follow_up_run(
                self.db,
                parent_run=self.parent,
                user=other,
                payload=self._payload(),
            )

    def test_rejects_when_conversation_has_active_run(self) -> None:
        active = NativeAgentRun(
            conversation_id=self.conversation.id,
            skill_version_id=self.version.id,
            status=AgentRunStatus.running,
            model_snapshot="test-model",
            model_route_snapshot="huomiao_responses",
            model_provider_snapshot="huomiao",
            model_api_shape_snapshot="responses",
            skill_name_snapshot=self.version.name_snapshot,
            skill_version_snapshot=self.version.version,
            skill_content_hash_snapshot=self.version.content_hash,
            style_reference_urls_json="[]",
        )
        self.db.add(active)
        self.db.commit()
        with self.assertRaisesRegex(NativeAgentFollowUpError, "仍有一轮正在运行"):
            create_follow_up_run(
                self.db,
                parent_run=self.parent,
                user=self.user,
                payload=self._payload(),
            )

    def test_rejects_context_that_cannot_be_copied_in_full(self) -> None:
        self.parent.final_output = "很长" * 100
        self.db.commit()
        with patch(
            "app.services.native_agent_follow_up.FOLLOW_UP_CONTEXT_MAX_BYTES",
            100,
        ):
            with self.assertRaisesRegex(NativeAgentFollowUpError, "超过 64000 字节"):
                create_follow_up_run(
                    self.db,
                    parent_run=self.parent,
                    user=self.user,
                    payload=self._payload(),
                )

    def test_siliconflow_s03_parent_rejects_follow_up_without_child(self) -> None:
        self.parent.model_route_snapshot = "siliconflow_chat_v1"
        self.parent.model_provider_snapshot = "siliconflow"
        self.parent.model_api_shape_snapshot = "chat_completions"
        self.parent.model_snapshot = "deepseek-ai/DeepSeek-V3.2"
        self.db.commit()
        before = self.db.query(NativeAgentRun).count()

        with self.assertRaisesRegex(
            NativeAgentFollowUpError,
            "不允许创建 Follow-up",
        ):
            create_follow_up_run(
                self.db,
                parent_run=self.parent,
                user=self.user,
                payload=self._payload(key="follow-up-s03-blocked"),
            )

        self.assertEqual(before, self.db.query(NativeAgentRun).count())

    def test_non_article_follow_up_with_empty_workflow_reaches_native_loop(self) -> None:
        self.version.tool_names_json = "[]"
        child, _ = create_follow_up_run(
            self.db,
            parent_run=self.parent,
            user=self.user,
            payload=self._payload(),
        )
        self.db.commit()
        child_workflow = workflow_for_native_run(self.db, child.id)
        self.assertEqual(
            0,
            len(
                self.db.scalars(
                    select(DurableAgentTask).where(
                        DurableAgentTask.workflow_id == child_workflow.id
                    )
                ).all()
            ),
        )

        async def exercise_worker() -> AsyncMock:
            execute = AsyncMock()
            queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
            with (
                patch.object(native_agent_worker, "SessionLocal", self.Session),
                patch.object(native_agent_worker, "_queue", queue),
                patch.object(
                    native_agent_worker,
                    "execute_native_agent_run",
                    execute,
                ),
            ):
                worker_task = asyncio.create_task(native_agent_worker._worker_loop())
                try:
                    await queue.put(("run", child.id))
                    await queue.join()
                finally:
                    worker_task.cancel()
                    await asyncio.gather(worker_task, return_exceptions=True)
            return execute

        execute = asyncio.run(exercise_worker())
        execute.assert_awaited_once_with(child.id)


if __name__ == "__main__":
    unittest.main()
