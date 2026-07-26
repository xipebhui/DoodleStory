import asyncio
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from agents import ToolOutputImage, ToolOutputText
from agents.tool_context import ToolContext
import mlflow
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentRun,
    AgentSkill,
    AgentSkillVersion,
    GenerationTask,
    NativeAgentConversation,
    NativeAgentItem,
    NativeAgentRun,
    User,
    Style,
)
from app.models.enums import (
    AgentRunStatus,
    AgentSkillStatus,
    NativeAgentItemType,
    StorageBackend,
    StyleStatus,
)
from app.api.native_agent import create_native_agent_run
from app.schemas.native_agent import NativeAgentRunCreate
from app.services.image_generation import GeneratedImageFile
from app.services import agent_observability, native_agent_loop
from app.services.native_agent_loop import (
    NativeAgentLoopError,
    NativeImageToolContext,
    build_generate_image_tool,
    execute_native_agent_run,
)


class NativeAgentLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        agent_observability.reset_agent_observability_for_tests()
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def tearDown(self) -> None:
        mlflow.flush_trace_async_logging(terminate=True)
        agent_observability.reset_agent_observability_for_tests()

    def test_generate_image_is_real_function_tool_and_returns_image_to_model(self) -> None:
        recorded_items: list[tuple[NativeAgentItemType, dict[str, object]]] = []
        recorded_prompts: list[str] = []

        def fake_image_generator(**kwargs):
            recorded_prompts.append(str(kwargs["prompt"]))
            self.assertEqual("gpt-image-2", kwargs["image_model_name"])
            self.assertEqual("9:16", kwargs["aspect_ratio"])
            return GeneratedImageFile(
                storage_backend=StorageBackend.local,
                storage_key="generated_image/test.png",
                byte_size=10,
                checksum_sha256="a" * 64,
                content_type="image/png",
                original_filename="test.png",
                provider_request_id="provider-request",
                width=1024,
                height=1792,
            )

        async def record_item(item_type, payload):
            recorded_items.append((item_type, payload))

        async def record_image(prompt, generated):
            self.assertEqual("完整的图片提示词", prompt)
            self.assertEqual("provider-request", generated.provider_request_id)
            return "data:image/png;base64,aW1hZ2U="

        tool = build_generate_image_tool(
            NativeImageToolContext(
                run_id="run-1",
                image_model="gpt-image-2",
                aspect_ratio="9:16",
                style_name="测试风格",
                style_prompt="粗线条暖色",
                reference_urls=(),
            ),
            image_generator=fake_image_generator,
            record_item=record_item,
            record_image=record_image,
        )

        self.assertEqual("generate_image", tool.name)
        self.assertIn("Runtime 不会在背后拼接或改写 Prompt", tool.description)
        output = asyncio.run(
            tool.on_invoke_tool(
                ToolContext(
                    context=None,
                    tool_name="generate_image",
                    tool_call_id="call-1",
                    tool_arguments='{"prompt":"完整的图片提示词"}',
                ),
                json.dumps({"prompt": "完整的图片提示词"}),
            )
        )

        self.assertEqual(["完整的图片提示词"], recorded_prompts)
        self.assertEqual(
            [NativeAgentItemType.tool_call, NativeAgentItemType.tool_result],
            [item_type for item_type, _ in recorded_items],
        )
        self.assertIsInstance(output[0], ToolOutputText)
        self.assertIsInstance(output[1], ToolOutputImage)
        self.assertEqual("data:image/png;base64,aW1hZ2U=", output[1].image_url)

    def test_generate_image_requires_style_but_has_no_hidden_default(self) -> None:
        async def record_item(item_type, payload):
            del item_type, payload

        async def record_image(prompt, generated):
            del prompt, generated
            raise AssertionError("无 Style 时不应保存图片")

        def fail_generator(**kwargs):
            del kwargs
            raise AssertionError("无 Style 时不应调用 Provider")

        tool = build_generate_image_tool(
            NativeImageToolContext(
                run_id="run-2",
                image_model=None,
                aspect_ratio=None,
                style_name=None,
                style_prompt=None,
                reference_urls=(),
            ),
            image_generator=fail_generator,
            record_item=record_item,
            record_image=record_image,
        )

        with self.assertRaises(NativeAgentLoopError):
            asyncio.run(
                tool.on_invoke_tool(
                    ToolContext(
                        context=None,
                        tool_name="generate_image",
                        tool_call_id="call-2",
                        tool_arguments='{"prompt":"尝试生成"}',
                    ),
                    json.dumps({"prompt": "尝试生成"}),
                )
            )

    def test_runner_receives_one_real_tool_and_no_legacy_workflow(self) -> None:
        with self.Session() as db:
            user = User(email="native-loop@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            skill = AgentSkill(
                owner_user_id=user.id,
                slug="native-loop-test",
                name="最小生图",
                description="使用一个生图工具完成图片任务。",
                draft_instructions="# 方法\n需要图片时调用 generate_image。",
                draft_tool_names_json='["generate_image"]',
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
                content_hash="sha256:native-loop-test",
                published_by_user_id=user.id,
            )
            db.add(version)
            db.flush()
            skill.active_version_id = version.id
            conversation = NativeAgentConversation(
                owner_user_id=user.id,
                title="测试最小 Loop",
            )
            db.add(conversation)
            db.flush()
            run = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=version.id,
                status=AgentRunStatus.queued,
                model_snapshot="test-model",
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
                    payload_json='{"content":"只回答，不要生图"}',
                )
            )
            db.commit()
            run_id = run.id

        captured: dict[str, object] = {}

        async def fake_run(agent, input_value, *, run_config, max_turns):
            captured["agent"] = agent
            captured["input"] = input_value
            captured["run_config"] = run_config
            captured["max_turns"] = max_turns
            return SimpleNamespace(
                final_output="已完成纯文本回答",
                raw_responses=[SimpleNamespace()],
            )

        fake_client = SimpleNamespace(close=AsyncMock())
        settings = SimpleNamespace(
            text_fallback_api_key="test-key",
            text_fallback_openai_base_url="https://example.invalid/v1",
            agent_request_timeout_seconds=30,
            agent_model="test-model",
            app_env="test",
        )
        with (
            patch.object(native_agent_loop, "SessionLocal", self.Session),
            patch.object(native_agent_loop, "AsyncOpenAI", return_value=fake_client),
            patch.object(native_agent_loop, "OpenAIProvider", return_value=object()),
            patch.object(native_agent_loop.Runner, "run", side_effect=fake_run),
        ):
            asyncio.run(execute_native_agent_run(run_id, settings=settings))

        agent = captured["agent"]
        self.assertEqual(["generate_image"], [tool.name for tool in agent.tools])
        self.assertEqual("只回答，不要生图", captured["input"])
        self.assertEqual(12, captured["max_turns"])
        self.assertEqual(
            1,
            captured["run_config"].tool_execution.max_function_tool_concurrency,
        )
        with self.Session() as db:
            persisted = db.scalar(
                select(NativeAgentRun).where(NativeAgentRun.id == run_id)
            )
            self.assertEqual(AgentRunStatus.succeeded, persisted.status)
            self.assertEqual(0, persisted.image_call_count)
            self.assertEqual("已完成纯文本回答", persisted.final_output)

        runtime_source = inspect.getsource(native_agent_loop)
        self.assertNotIn("GenericToolExecutor", runtime_source)
        self.assertNotIn("GenerationTask", runtime_source)
        self.assertNotIn("ComicPlan", runtime_source)

    def test_new_run_persists_only_native_loop_state(self) -> None:
        with self.Session() as db:
            user = User(email="native-api@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            skill = AgentSkill(
                owner_user_id=user.id,
                slug="native-api-skill",
                name="原生图片 Skill",
                description="只使用 generate_image。",
                draft_instructions="# 方法\n调用生图后直接看图。",
                draft_tool_names_json='["generate_image"]',
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
                content_hash="sha256:native-api",
                published_by_user_id=user.id,
            )
            db.add(version)
            db.flush()
            skill.active_version_id = version.id
            style = Style(
                name="原生 Loop 测试风格",
                status=StyleStatus.active,
                image_model_name="gpt-image-2",
                aspect_ratio="9:16",
                style_prompt="简洁线稿",
            )
            conversation = NativeAgentConversation(
                owner_user_id=user.id,
                title="原生 API",
            )
            db.add_all([style, conversation])
            db.commit()

            with patch(
                "app.api.native_agent.execute_native_agent_run",
                new=AsyncMock(),
            ) as execute:
                response = asyncio.run(
                    create_native_agent_run(
                        conversation.id,
                        NativeAgentRunCreate(
                            content="生成一张开场图",
                            skill_version_id=version.id,
                            style_id=style.id,
                        ),
                        user,
                        db,
                    )
                )

            execute.assert_awaited_once()
            self.assertEqual(AgentRunStatus.queued, response.data.status)
            self.assertEqual(1, db.query(NativeAgentRun).count())
            self.assertEqual(0, db.query(AgentRun).count())
            self.assertEqual(0, db.query(GenerationTask).count())

    def test_native_run_trace_covers_model_tool_provider_and_redacts_content(self) -> None:
        with self.Session() as db:
            user = User(email="native-trace@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            skill = AgentSkill(
                owner_user_id=user.id,
                slug="native-trace-skill",
                name="原生追踪 Skill",
                description="只使用 generate_image。",
                draft_instructions="# 方法\n调用生图并查看结果。",
                draft_tool_names_json='["generate_image"]',
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
                content_hash="sha256:native-trace",
                published_by_user_id=user.id,
            )
            db.add(version)
            db.flush()
            skill.active_version_id = version.id
            conversation = NativeAgentConversation(
                owner_user_id=user.id,
                title="Native Trace",
            )
            db.add(conversation)
            db.flush()
            run = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=version.id,
                status=AgentRunStatus.queued,
                model_snapshot="test-model",
                skill_name_snapshot=version.name_snapshot,
                skill_version_snapshot=version.version,
                skill_content_hash_snapshot=version.content_hash,
                style_name_snapshot="测试视觉",
                style_prompt_snapshot="private style instructions",
                image_model_snapshot="gpt-image-2",
                aspect_ratio_snapshot="9:16",
                style_reference_urls_json="[]",
            )
            db.add(run)
            db.flush()
            db.add(
                NativeAgentItem(
                    run_id=run.id,
                    sequence=1,
                    item_type=NativeAgentItemType.user_input,
                    payload_json=json.dumps(
                        {"content": "private native user content"},
                        ensure_ascii=False,
                    ),
                )
            )
            db.commit()
            run_id = run.id

        generated = GeneratedImageFile(
            storage_backend=StorageBackend.local,
            storage_key="generated_image/native-trace.png",
            public_url="https://private.example/native-trace.png",
            byte_size=10,
            checksum_sha256="b" * 64,
            content_type="image/png",
            original_filename="native-trace.png",
            provider_request_id="provider-native-trace",
            width=1024,
            height=1792,
        )

        async def fake_run(agent, input_value, *, run_config, max_turns):
            del input_value, run_config, max_turns
            output = await agent.tools[0].on_invoke_tool(
                ToolContext(
                    context=None,
                    tool_name="generate_image",
                    tool_call_id="trace-tool-call",
                    tool_arguments='{"prompt":"private image prompt"}',
                ),
                json.dumps({"prompt": "private image prompt"}),
            )
            self.assertIsInstance(output[1], ToolOutputImage)
            return SimpleNamespace(
                final_output="private native final output",
                raw_responses=[SimpleNamespace(), SimpleNamespace()],
            )

        fake_client = SimpleNamespace(close=AsyncMock())
        with TemporaryDirectory() as temp_dir:
            tracking_uri = f"sqlite:///{Path(temp_dir) / 'mlflow.db'}"
            settings = SimpleNamespace(
                mlflow_tracing_enabled=True,
                mlflow_tracking_uri=tracking_uri,
                mlflow_experiment_name="native-agent-observability-tests",
                mlflow_trace_content=False,
                text_fallback_api_key="private-primary-secret",
                lio_api_key="private-fallback-secret",
                image_gateway_api_key="private-image-secret",
                text_fallback_openai_base_url="https://private.example/v1",
                agent_request_timeout_seconds=30,
                agent_model="test-model",
                app_env="test",
            )
            agent_observability.initialize_agent_observability(settings)
            with (
                patch.object(native_agent_loop, "SessionLocal", self.Session),
                patch.object(
                    native_agent_loop,
                    "AsyncOpenAI",
                    return_value=fake_client,
                ),
                patch.object(
                    native_agent_loop,
                    "OpenAIProvider",
                    return_value=object(),
                ),
                patch.object(
                    native_agent_loop.Runner,
                    "run",
                    side_effect=fake_run,
                ),
            ):
                asyncio.run(
                    execute_native_agent_run(
                        run_id,
                        settings=settings,
                        image_generator=lambda **kwargs: generated,
                    )
                )
            mlflow.flush_trace_async_logging()
            experiment = mlflow.get_experiment_by_name(
                settings.mlflow_experiment_name
            )
            traces = mlflow.search_traces(
                locations=[experiment.experiment_id],
                filter_string=f"tags.native_agent_run_id = '{run_id}'",
                return_type="list",
                include_spans=True,
                flush=True,
            )

            self.assertEqual(1, len(traces))
            spans = traces[0].data.spans
            span_names = [span.name for span in spans]
            self.assertIn("native_agent.run", span_names)
            self.assertIn("native_agent.model_loop", span_names)
            self.assertIn("native_agent.generate_image", span_names)
            self.assertIn("native_agent.image_provider", span_names)
            root_span = next(
                span for span in spans if span.name == "native_agent.run"
            )
            self.assertEqual("succeeded", root_span.attributes["run_status"])
            self.assertEqual(2, root_span.attributes["model_call_count"])
            self.assertEqual(1, root_span.attributes["image_call_count"])
            serialized = json.dumps(traces[0].to_dict())
            self.assertNotIn("private native user content", serialized)
            self.assertNotIn("private image prompt", serialized)
            self.assertNotIn("private native final output", serialized)
            self.assertNotIn("private style instructions", serialized)
            self.assertNotIn("private.example", serialized)
            self.assertNotIn("private-primary-secret", serialized)
