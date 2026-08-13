import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agents.usage import Usage
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    NativeAgentArticleApproval,
    NativeAgentArtifact,
    NativeAgentContextItem,
    NativeAgentConversation,
    NativeAgentEvent,
    NativeAgentItem,
    NativeAgentRun,
    User,
)
from app.models.enums import (
    AgentRunStatus,
    AgentSkillStatus,
    NativeAgentItemType,
)
from app.api.native_agent import decide_native_article_approval
from app.schemas.native_agent import NativeAgentArticleApprovalDecision
from app.services.native_agent_loop import (
    CompiledArticleWorkflow,
    NativeModelMetricHooks,
    article_role_instructions,
    build_article_agent_tools,
)
from app.services.native_agent_persistence import NativeAgentStore
from app.services.native_article_workflow import (
    ARTICLE_DRAFT,
    ARTICLE_REVIEW,
    decide_article_approval,
    load_compiled_workflow_plan,
    request_final_article_approval,
    save_article_artifact,
    save_compiled_workflow_plan,
)


class NativeArticleWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
        )

    def create_run(
        self,
        *,
        email: str,
        session_factory=None,
    ) -> tuple[str, str]:
        resolved_session_factory = session_factory or self.Session
        with resolved_session_factory() as db:
            user = User(email=email, password_hash="hash")
            db.add(user)
            db.flush()
            skill = AgentSkill(
                owner_user_id=user.id,
                slug=f"article-team-{user.id}",
                name="多 Agent 文案创作",
                description="测试文案工作流。",
                draft_instructions="# Director\n调用 Writer 和 Reviewer。",
                draft_tool_names_json=(
                    '["write_article","review_article","submit_final_article"]'
                ),
                draft_revision=1,
                status=AgentSkillStatus.published,
            )
            db.add(skill)
            db.flush()
            version = AgentSkillVersion(
                skill_id=skill.id,
                version=1,
                name_snapshot=skill.name,
                description_snapshot=skill.description,
                instructions=skill.draft_instructions,
                tool_names_json=skill.draft_tool_names_json,
                content_hash="sha256:article-team",
                published_by_user_id=user.id,
            )
            db.add(version)
            db.flush()
            skill.active_version_id = version.id
            conversation = NativeAgentConversation(
                owner_user_id=user.id,
                title="文案测试",
            )
            db.add(conversation)
            db.flush()
            run = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=version.id,
                status=AgentRunStatus.running,
                model_snapshot="test-model",
                model_route_snapshot="huomiao_responses",
                model_provider_snapshot="huomiao",
                model_api_shape_snapshot="responses",
                skill_name_snapshot=version.name_snapshot,
                skill_version_snapshot=version.version,
                skill_content_hash_snapshot=version.content_hash,
                style_reference_urls_json="[]",
            )
            db.add(run)
            db.flush()
            db.add(
                NativeAgentItem(
                    run_id=run.id,
                    sequence=1,
                    item_type=NativeAgentItemType.user_input,
                    payload_json='{"content":"写一篇关于慢生活的短文"}',
                )
            )
            db.commit()
            return run.id, user.id

    def test_child_artifacts_and_change_request_resume_same_run(self) -> None:
        run_id, user_id = self.create_run(email="changes@example.com")
        draft = save_article_artifact(
            run_id,
            artifact_type=ARTICLE_DRAFT,
            producer_role="writer",
            content={
                "title": "慢下来",
                "body_markdown": "第一版正文",
                "creative_summary": "从通勤切入",
                "hook": "你多久没有慢慢吃一顿饭？",
            },
            session_factory=self.Session,
        )
        review = save_article_artifact(
            run_id,
            artifact_type=ARTICLE_REVIEW,
            producer_role="reviewer",
            content={
                "verdict": "changes_required",
                "summary": "结尾需要更具体。",
                "strengths": ["开头明确"],
                "issues": ["结尾抽象"],
            },
            session_factory=self.Session,
        )
        requested = request_final_article_approval(
            run_id,
            title="慢下来",
            body_markdown="第一版正文",
            session_factory=self.Session,
        )
        NativeAgentStore(
            run_id,
            session_factory=self.Session,
        ).pause_for_article_approval("等待用户审批")

        self.assertEqual(ARTICLE_DRAFT, draft["artifact_type"])
        self.assertEqual(ARTICLE_REVIEW, review["artifact_type"])
        run_after_decision, decision = decide_article_approval(
            str(requested["approval_id"]),
            user_id=user_id,
            decision="changes_requested",
            feedback="保留开头，把结尾改成三个可执行动作。",
            session_factory=self.Session,
        )

        self.assertEqual(run_id, run_after_decision)
        self.assertEqual("changes_requested", decision)
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            self.assertIsNotNone(run)
            self.assertEqual(AgentRunStatus.retrying, run.status)
            self.assertEqual("revising_article", run.workflow_phase)
            self.assertEqual(1, run.workflow_revision)
            artifacts = db.scalars(
                select(NativeAgentArtifact).where(
                    NativeAgentArtifact.run_id == run_id
                )
            ).all()
            self.assertEqual(3, len(artifacts))
            context = db.scalar(
                select(NativeAgentContextItem).where(
                    NativeAgentContextItem.run_id == run_id
                )
            )
            self.assertIsNotNone(context)
            self.assertIn(
                "三个可执行动作",
                json.loads(context.item_json)["content"],
            )

    def test_approve_final_article_completes_text_only_run(self) -> None:
        run_id, user_id = self.create_run(email="approve@example.com")
        requested = request_final_article_approval(
            run_id,
            title="一封写给忙碌者的信",
            body_markdown="先把今天过慢一点。",
            session_factory=self.Session,
        )
        NativeAgentStore(
            run_id,
            session_factory=self.Session,
        ).pause_for_article_approval("等待用户审批")

        decide_article_approval(
            str(requested["approval_id"]),
            user_id=user_id,
            decision="approve",
            feedback=None,
            session_factory=self.Session,
        )

        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            approval = db.get(
                NativeAgentArticleApproval,
                str(requested["approval_id"]),
            )
            self.assertIsNotNone(run)
            self.assertIsNotNone(approval)
            self.assertEqual(AgentRunStatus.succeeded, run.status)
            self.assertEqual("article_approved", run.workflow_phase)
            self.assertEqual("先把今天过慢一点。", run.final_output)
            self.assertEqual("approved", approval.status)
            self.assertEqual(0, run.image_call_count)
            self.assertEqual(0, run.speech_call_count)
            self.assertEqual(0, run.subtitle_call_count)
            self.assertEqual(0, run.video_call_count)

    def test_article_skill_builds_sdk_agents_as_tools(self) -> None:
        run_id, _ = self.create_run(email="tools@example.com")
        workflow = CompiledArticleWorkflow.model_validate(
            {
                "workflow_summary": "先写作，再审稿，最后提交审批。",
                "shared_constraints": ["只生成文本。"],
                "roles": [
                    {
                        "name": "director",
                        "mission": "协调文案工作流。",
                        "instructions": ["调用子 Agent，不直接跳过。"],
                    },
                    {
                        "name": "writer",
                        "mission": "完成文章草稿。",
                        "instructions": ["写出完整正文。"],
                    },
                    {
                        "name": "reviewer",
                        "mission": "独立审稿。",
                        "instructions": ["只指出影响交付的问题。"],
                    },
                ],
                "execution_steps": [
                    {
                        "sequence": 1,
                        "tool_name": "write_article",
                        "objective": "取得草稿。",
                        "required_inputs": ["用户要求"],
                        "completion_condition": "草稿 Artifact 已保存。",
                    },
                    {
                        "sequence": 2,
                        "tool_name": "review_article",
                        "objective": "完成审稿。",
                        "required_inputs": ["用户要求", "草稿"],
                        "completion_condition": "审稿 Artifact 已保存。",
                    },
                    {
                        "sequence": 3,
                        "tool_name": "submit_final_article",
                        "objective": "提交最终文案。",
                        "required_inputs": ["标题", "正文"],
                        "completion_condition": "进入用户审批。",
                    },
                ],
                "quality_gates": ["文章满足用户要求。"],
            }
        )
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            self.assertIsNotNone(run)
            run.creation_channel_context_json = json.dumps(
                {
                    "status": "resolved",
                    "matched_by": "selected_account_id",
                    "account": {
                        "account_id": "account-1",
                        "alias": "历史商业取证",
                    },
                    "content_strategy": {
                        "account_positioning": "从历史事实解释商业选择",
                        "target_audience": "商业史观众",
                    },
                },
                ensure_ascii=False,
            )
            run.skill_version
            store = NativeAgentStore(run_id, session_factory=self.Session)
            tools = build_article_agent_tools(
                run,
                workflow=workflow,
                model="test-model",
                store=store,
                hooks=NativeModelMetricHooks(store, phase="test"),
            )
            writer_instructions = article_role_instructions(
                run,
                workflow,
                active_role="writer",
            )

        self.assertEqual(
            {"write_article", "review_article", "submit_final_article"},
            {tool.name for tool in tools},
        )
        self.assertIn("写出完整正文", writer_instructions)
        self.assertIn("<creation_account_context>", writer_instructions)
        self.assertIn("历史商业取证", writer_instructions)
        self.assertIn("从历史事实解释商业选择", writer_instructions)
        self.assertNotIn("协调文案工作流", writer_instructions)
        self.assertNotIn("独立审稿", writer_instructions)

    def test_compiled_workflow_is_persisted_and_reused_by_skill_hash(self) -> None:
        run_id, _ = self.create_run(email="compiled-plan@example.com")
        plan = {
            "workflow_summary": "模型编译后的计划",
            "roles": [{"name": "director"}],
        }
        save_compiled_workflow_plan(
            run_id,
            skill_content_hash="sha256:article-team",
            plan=plan,
            session_factory=self.Session,
        )

        loaded = load_compiled_workflow_plan(
            run_id,
            skill_content_hash="sha256:article-team",
            session_factory=self.Session,
        )

        self.assertEqual(plan, loaded)
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            events = db.scalars(
                select(NativeAgentEvent).where(
                    NativeAgentEvent.run_id == run_id,
                    NativeAgentEvent.event_type == "workflow.compiled",
                )
            ).all()
            self.assertEqual("workflow_compiled", run.workflow_phase)
            self.assertEqual(1, len(events))

    def test_model_request_metric_counts_concurrent_child_calls(self) -> None:
        database_path = Path(self._testMethodName + ".db")
        with TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            engine = create_engine(
                f"sqlite:///{Path(temp_dir) / database_path}",
                connect_args={"check_same_thread": False, "timeout": 30},
            )
            Base.metadata.create_all(engine)
            session_factory = sessionmaker(
                bind=engine,
                autoflush=False,
                autocommit=False,
            )
            run_id, _ = self.create_run(
                email="metric-concurrency@example.com",
                session_factory=session_factory,
            )
            store = NativeAgentStore(run_id, session_factory=session_factory)

            def record(index: int) -> None:
                store.record_model_request_started(
                    metric_call_id=f"metric-{index}",
                    role="writer" if index % 2 else "reviewer",
                    phase="test",
                )

            with ThreadPoolExecutor(max_workers=6) as executor:
                list(executor.map(record, range(6)))

            with session_factory() as db:
                run = db.get(NativeAgentRun, run_id)
                events = db.scalars(
                    select(NativeAgentEvent).where(
                        NativeAgentEvent.run_id == run_id,
                        NativeAgentEvent.event_type == "model.request.started",
                    )
                ).all()
                self.assertEqual(6, run.model_call_count)
                self.assertEqual(6, len(events))

    def test_model_metric_pairs_sdk_callbacks_across_async_tasks(self) -> None:
        run_id, _ = self.create_run(email="metric-hooks@example.com")
        store = NativeAgentStore(run_id, session_factory=self.Session)
        hooks = NativeModelMetricHooks(store, phase="test")
        agent = SimpleNamespace(name="DoodleStoryArticleWorkflowCompiler")

        async def invoke_callbacks() -> None:
            await asyncio.create_task(
                hooks.on_llm_start(None, agent, None, [])
            )
            await asyncio.create_task(
                hooks.on_llm_end(
                    None,
                    agent,
                    SimpleNamespace(usage=Usage(requests=1)),
                )
            )

        asyncio.run(invoke_callbacks())

        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            events = db.scalars(
                select(NativeAgentEvent).where(
                    NativeAgentEvent.run_id == run_id,
                    NativeAgentEvent.event_type.in_(
                        ("model.request.started", "model.request.completed")
                    ),
                )
            ).all()
            self.assertEqual(1, run.model_call_count)
            self.assertEqual(2, len(events))
            self.assertEqual(1, hooks.completed_count)

    def test_approval_api_is_owner_scoped_and_returns_fresh_state(self) -> None:
        run_id, user_id = self.create_run(email="api-owner@example.com")
        requested = request_final_article_approval(
            run_id,
            title="API 文案",
            body_markdown="只返回文本。",
            session_factory=self.Session,
        )
        NativeAgentStore(
            run_id,
            session_factory=self.Session,
        ).pause_for_article_approval("等待用户审批")
        with self.Session() as db:
            owner = db.get(User, user_id)
            self.assertIsNotNone(owner)
            with patch("app.api.native_agent.SessionLocal", self.Session):
                response = asyncio.run(
                    decide_native_article_approval(
                        str(requested["approval_id"]),
                        NativeAgentArticleApprovalDecision(
                            decision="approve",
                            feedback=None,
                        ),
                        user=owner,
                        db=db,
                    )
                )
            self.assertEqual(AgentRunStatus.succeeded, response.data.status)
            self.assertEqual(
                "approved",
                response.data.artifacts[-1].approval.status,
            )

        _, other_user_id = self.create_run(email="api-other@example.com")
        with self.Session() as db:
            other_user = db.get(User, other_user_id)
            self.assertIsNotNone(other_user)
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    decide_native_article_approval(
                        str(requested["approval_id"]),
                        NativeAgentArticleApprovalDecision(
                            decision="approve",
                            feedback=None,
                        ),
                        user=other_user,
                        db=db,
                    )
                )
            self.assertEqual(404, raised.exception.status_code)

    def test_parent_stream_and_child_artifact_allocate_unique_events(self) -> None:
        with TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            database_path = Path(temp_dir) / "concurrent-events.db"
            engine = create_engine(
                f"sqlite:///{database_path}",
                connect_args={
                    "check_same_thread": False,
                    "timeout": 10,
                },
            )
            Base.metadata.create_all(engine)
            session_factory = sessionmaker(
                bind=engine,
                autoflush=False,
                autocommit=False,
            )
            run_id, _ = self.create_run(
                email="concurrent-events@example.com",
                session_factory=session_factory,
            )

            def append_parent_events() -> None:
                store = NativeAgentStore(
                    run_id,
                    session_factory=session_factory,
                )
                for index in range(40):
                    store.append_event(
                        "response.function_call.arguments.delta",
                        {"index": index},
                    )

            def append_child_artifacts() -> None:
                for index in range(20):
                    save_article_artifact(
                        run_id,
                        artifact_type=ARTICLE_DRAFT,
                        producer_role="writer",
                        content={
                            "title": f"并发草稿 {index}",
                            "body_markdown": f"正文 {index}",
                            "creative_summary": "并发测试",
                            "hook": "测试钩子",
                        },
                        session_factory=session_factory,
                    )

            with ThreadPoolExecutor(max_workers=2) as executor:
                parent_future = executor.submit(append_parent_events)
                child_future = executor.submit(append_child_artifacts)
                parent_future.result()
                child_future.result()

            with session_factory() as db:
                run = db.get(NativeAgentRun, run_id)
                sequences = list(
                    db.scalars(
                        select(NativeAgentEvent.sequence)
                        .where(NativeAgentEvent.run_id == run_id)
                        .order_by(NativeAgentEvent.sequence)
                    ).all()
                )
                self.assertIsNotNone(run)
                self.assertEqual(list(range(1, 61)), sequences)
                self.assertEqual(60, run.event_sequence)


if __name__ == "__main__":
    unittest.main()
