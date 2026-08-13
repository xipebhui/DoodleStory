import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.native_agent import create_native_agent_run
from app.core.config import Settings
from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    DurableAgentWorkflow,
    NativeAgentConversation,
    NativeAgentItem,
    NativeAgentRun,
    User,
)
from app.models.enums import AgentRunStatus, AgentSkillStatus, NativeAgentItemType
from app.schemas.native_agent import NativeAgentRunCreate
from app.services.agent_model_router import AgentModelRouter
from app.services import native_agent_loop, native_agent_model_routes
from app.services.native_agent_loop import execute_native_agent_run
from app.services.native_agent_loop import CompiledArticleWorkflow
from app.services.native_agent_model_routes import (
    NativeAgentModelRouteConfigError,
    NativeAgentModelRouteSnapshotError,
    resolve_default_native_agent_model_route,
)


class FakeStreamedResult:
    final_output = "使用 Run 快照完成"
    raw_responses = [SimpleNamespace()]

    async def stream_events(self):
        response = SimpleNamespace(id="response-route-test", usage=None)
        yield SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(type="response.created", response=response),
        )
        yield SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(type="response.completed", response=response),
        )


def settings(**overrides) -> Settings:
    values = {
        "session_secret": "route-test-secret",
        "text_fallback_api_key": "huomiao-secret",
        "text_fallback_base_url": "https://huomiao.example/v1",
        "agent_model": "legacy-router-model",
        "native_agent_default_route": "huomiao_responses",
        "native_agent_huomiao_model": "native-snapshot-model",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class NativeAgentModelRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        with self.Session() as db:
            self.user = User(email="route@example.com", password_hash="hash")
            db.add(self.user)
            db.flush()
            skill = AgentSkill(
                owner_user_id=self.user.id,
                slug="route-test",
                name="路由测试",
                description="验证 Native Agent 路由快照。",
                draft_instructions="只回复完成。",
                draft_tool_names_json="[]",
                draft_revision=1,
                status=AgentSkillStatus.published,
            )
            db.add(skill)
            db.flush()
            self.version = AgentSkillVersion(
                skill_id=skill.id,
                version=1,
                name_snapshot=skill.name,
                description_snapshot=skill.description,
                instructions=skill.draft_instructions,
                tool_names_json="[]",
                content_hash="sha256:route-test",
                published_by_user_id=self.user.id,
            )
            db.add(self.version)
            db.flush()
            skill.active_version_id = self.version.id
            self.conversation = NativeAgentConversation(
                owner_user_id=self.user.id,
                title="路由测试",
            )
            db.add(self.conversation)
            db.commit()
            for value in (self.user, self.version, self.conversation):
                db.refresh(value)
                db.expunge(value)

    def test_default_route_is_independent_from_legacy_agent_model(self) -> None:
        selected = settings(
            agent_model="legacy-only",
            native_agent_huomiao_model="native-only",
            lio_api_key="lio-secret",
            lio_base_url="https://lio.example/v1",
        )
        snapshot = resolve_default_native_agent_model_route(selected)
        router = AgentModelRouter(selected)

        self.assertEqual("legacy-only", router.model)
        self.assertEqual("native-only", snapshot.model)
        self.assertEqual("huomiao_responses", snapshot.route)
        self.assertEqual("huomiao", snapshot.provider)
        self.assertEqual("responses", snapshot.api_shape)

    def test_invalid_default_route_config_is_rejected_without_secret_values(self) -> None:
        cases = (
            (settings(native_agent_default_route="siliconflow_chat_v1"), "默认路由"),
            (settings(native_agent_huomiao_model=" "), "NATIVE_AGENT_HUOMIAO_MODEL"),
            (settings(text_fallback_api_key=" "), "TEXT_FALLBACK_API_KEY"),
            (settings(text_fallback_base_url="not-a-url"), "TEXT_FALLBACK_BASE_URL"),
            (
                settings(text_fallback_base_url="https://example.com:bad/v1"),
                "TEXT_FALLBACK_BASE_URL",
            ),
            (
                settings(
                    text_fallback_base_url="https://user:secret@huomiao.example/v1"
                ),
                "TEXT_FALLBACK_BASE_URL",
            ),
        )
        for selected, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(
                    NativeAgentModelRouteConfigError,
                    expected,
                ):
                    resolve_default_native_agent_model_route(selected)

    def test_create_run_persists_route_projection_and_config_error_writes_nothing(
        self,
    ) -> None:
        payload = NativeAgentRunCreate(
            content="验证路由",
            skill_version_id=self.version.id,
        )
        with self.Session() as db:
            with (
                patch(
                    "app.api.native_agent.get_settings",
                    return_value=settings(),
                ),
                patch(
                    "app.api.native_agent.enqueue_native_agent_run",
                    new=AsyncMock(),
                ) as enqueue,
            ):
                response = asyncio.run(
                    create_native_agent_run(
                        self.conversation.id,
                        payload,
                        self.user,
                        db,
                    )
                )
            enqueue.assert_awaited_once_with(response.data.id)
            self.assertEqual("huomiao_responses", response.data.model_route)
            self.assertEqual("huomiao", response.data.model_provider)
            self.assertEqual("responses", response.data.model_api_shape)
            self.assertEqual("native-snapshot-model", response.data.model)

        with self.Session() as db:
            run = db.get(NativeAgentRun, response.data.id)
            run.status = AgentRunStatus.succeeded
            db.commit()
            before = (
                db.query(NativeAgentRun).count(),
                db.query(NativeAgentItem).count(),
                db.query(DurableAgentWorkflow).count(),
            )
            with (
                patch(
                    "app.api.native_agent.get_settings",
                    return_value=settings(native_agent_default_route="unknown"),
                ),
                patch(
                    "app.api.native_agent.enqueue_native_agent_run",
                    new=AsyncMock(),
                ) as enqueue,
            ):
                with self.assertRaises(HTTPException) as caught:
                    asyncio.run(
                        create_native_agent_run(
                            self.conversation.id,
                            payload,
                            self.user,
                            db,
                        )
                    )
            self.assertEqual(503, caught.exception.status_code)
            enqueue.assert_not_awaited()
            after = (
                db.query(NativeAgentRun).count(),
                db.query(NativeAgentItem).count(),
                db.query(DurableAgentWorkflow).count(),
            )
            self.assertEqual(before, after)

    def _create_queued_run(self, *, model: str = "persisted-run-model") -> str:
        with self.Session() as db:
            run = NativeAgentRun(
                conversation_id=self.conversation.id,
                skill_version_id=self.version.id,
                status=AgentRunStatus.queued,
                model_snapshot=model,
                model_route_snapshot="huomiao_responses",
                model_provider_snapshot="huomiao",
                model_api_shape_snapshot="responses",
                skill_name_snapshot=self.version.name_snapshot,
                skill_version_snapshot=self.version.version,
                skill_content_hash_snapshot=self.version.content_hash,
                style_reference_urls_json="[]",
            )
            db.add(run)
            db.flush()
            db.add(
                NativeAgentItem(
                    run_id=run.id,
                    sequence=1,
                    item_type=NativeAgentItemType.user_input,
                    payload_json='{"content":"执行快照"}',
                )
            )
            db.commit()
            return run.id

    def test_execution_uses_run_model_after_environment_models_change(self) -> None:
        run_id = self._create_queued_run()
        captured: dict[str, object] = {}

        def fake_run_streamed(agent, input_value, **kwargs):
            captured["model"] = agent.model
            captured["input"] = input_value
            captured["provider"] = kwargs["run_config"].model_provider
            return FakeStreamedResult()

        fake_client = SimpleNamespace(close=AsyncMock())
        changed = settings(
            agent_model="changed-legacy-model",
            native_agent_huomiao_model="changed-native-default",
        )
        with (
            patch.object(native_agent_loop, "SessionLocal", self.Session),
            patch.object(
                native_agent_model_routes,
                "AsyncOpenAI",
                return_value=fake_client,
            ),
            patch.object(
                native_agent_model_routes,
                "OpenAIProvider",
                return_value="run-provider",
            ),
            patch.object(
                native_agent_loop.Runner,
                "run_streamed",
                side_effect=fake_run_streamed,
            ),
        ):
            asyncio.run(execute_native_agent_run(run_id, settings=changed))

        self.assertEqual("persisted-run-model", captured["model"])
        self.assertEqual("执行快照", captured["input"])
        self.assertEqual("run-provider", captured["provider"])
        fake_client.close.assert_awaited_once()
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            self.assertEqual(AgentRunStatus.succeeded, run.status)
            self.assertEqual("persisted-run-model", run.model_snapshot)

    def test_unknown_or_contradictory_persisted_route_fails_closed(self) -> None:
        run_id = self._create_queued_run()
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            run.model_api_shape_snapshot = "chat_completions"
            db.commit()
        with (
            patch.object(native_agent_loop, "SessionLocal", self.Session),
            patch.object(native_agent_model_routes, "AsyncOpenAI") as client,
            patch.object(native_agent_loop.Runner, "run_streamed") as runner,
        ):
            asyncio.run(execute_native_agent_run(run_id, settings=settings()))

        client.assert_not_called()
        runner.assert_not_called()
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            self.assertEqual(AgentRunStatus.failed, run.status)
            self.assertEqual(
                NativeAgentModelRouteSnapshotError.__name__,
                run.error_code,
            )
            self.assertIn("未知或互相矛盾", run.error_message)

    def test_article_compiler_director_and_role_factory_use_run_model(self) -> None:
        with self.Session() as db:
            version = db.get(AgentSkillVersion, self.version.id)
            version.tool_names_json = (
                '["write_article","review_article","submit_final_article"]'
            )
            db.commit()
        run_id = self._create_queued_run(model="article-run-model")
        workflow = CompiledArticleWorkflow.model_validate(
            {
                "workflow_summary": "写作、审稿、提交。",
                "shared_constraints": ["只生成文本。"],
                "roles": [
                    {
                        "name": "director",
                        "mission": "协调。",
                        "instructions": ["按顺序调用。"],
                    },
                    {
                        "name": "writer",
                        "mission": "写作。",
                        "instructions": ["写正文。"],
                    },
                    {
                        "name": "reviewer",
                        "mission": "审稿。",
                        "instructions": ["独立审核。"],
                    },
                ],
                "execution_steps": [
                    {
                        "sequence": 1,
                        "tool_name": "write_article",
                        "objective": "写草稿。",
                        "required_inputs": ["要求"],
                        "completion_condition": "有草稿。",
                    },
                    {
                        "sequence": 2,
                        "tool_name": "review_article",
                        "objective": "审稿。",
                        "required_inputs": ["草稿"],
                        "completion_condition": "有审稿。",
                    },
                    {
                        "sequence": 3,
                        "tool_name": "submit_final_article",
                        "objective": "提交。",
                        "required_inputs": ["正文"],
                        "completion_condition": "已提交。",
                    },
                ],
                "quality_gates": ["满足用户要求。"],
            }
        )
        captured: dict[str, object] = {}

        def fake_build_article_tools(run, **kwargs):
            captured["roles_model"] = kwargs["model"]
            return []

        def fake_run_streamed(agent, input_value, **kwargs):
            captured["director_model"] = agent.model
            return FakeStreamedResult()

        fake_client = SimpleNamespace(close=AsyncMock())
        with (
            patch.object(native_agent_loop, "SessionLocal", self.Session),
            patch.object(
                native_agent_model_routes,
                "AsyncOpenAI",
                return_value=fake_client,
            ),
            patch.object(
                native_agent_model_routes,
                "OpenAIProvider",
                return_value=object(),
            ),
            patch.object(
                native_agent_loop,
                "compile_article_workflow",
                new=AsyncMock(return_value=workflow),
            ) as compiler,
            patch.object(
                native_agent_loop,
                "build_article_agent_tools",
                side_effect=fake_build_article_tools,
            ),
            patch.object(
                native_agent_loop.Runner,
                "run_streamed",
                side_effect=fake_run_streamed,
            ),
        ):
            asyncio.run(
                execute_native_agent_run(
                    run_id,
                    settings=settings(
                        agent_model="changed-legacy",
                        native_agent_huomiao_model="changed-native",
                    ),
                )
            )

        self.assertEqual("article-run-model", compiler.await_args.kwargs["model"])
        self.assertEqual("article-run-model", captured["roles_model"])
        self.assertEqual("article-run-model", captured["director_model"])


if __name__ == "__main__":
    unittest.main()
