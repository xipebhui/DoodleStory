import asyncio
from datetime import datetime
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from agents import ToolOutputImage, ToolOutputText
from agents.tool_context import ToolContext
from fastapi import HTTPException
import mlflow
from mlflow.entities import SpanStatusCode
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentRun,
    AgentSkill,
    AgentSkillVersion,
    FileAsset,
    GenerationTask,
    NativeAgentConversation,
    NativeAgentAudio,
    NativeAgentContextItem,
    NativeAgentEvent,
    NativeAgentItem,
    NativeAgentRun,
    NativeAgentStep,
    NativeAgentVideo,
    User,
    Style,
)
from app.models.enums import (
    AgentRunStatus,
    AgentSkillStatus,
    NativeAgentItemType,
    NativeAgentStepStatus,
    NativeAgentStepType,
    StorageBackend,
    StyleStatus,
)
from app.api.native_agent import (
    create_native_agent_run,
    stream_native_agent_run_events,
)
from app.api.assets import can_read_asset
from app.schemas.native_agent import NativeAgentRunCreate
from app.services.image_generation import (
    GeneratedImageFile,
    ImageProviderResponseError,
)
from app.services import agent_observability, native_agent_loop, native_agent_worker
from app.services.native_agent_loop import (
    NativeAgentLoopError,
    NativeImageToolContext,
    build_generate_image_tool,
    build_generate_speech_tool,
    build_render_story_video_tool,
    execute_native_agent_run,
    native_agent_instructions,
    native_runtime_tool_names,
)
from app.services.native_agent_persistence import (
    CompletedNativeSpeech,
    CompletedNativeTool,
    NativeAgentDatabaseSession,
    NativeAgentStore,
)
from app.services.storage import StoredFile
from app.services.volcengine_speech import GeneratedSpeech
from app.services.remotion_video import GeneratedRemotionVideo, RemotionScene


class FakeStreamedResult:
    def __init__(
        self,
        *,
        final_output: str,
        raw_response_count: int,
        events: list[object] | None = None,
        on_stream=None,
    ) -> None:
        self.final_output = final_output
        self.raw_responses = [SimpleNamespace()] * raw_response_count
        self._events = events or []
        self._on_stream = on_stream

    async def stream_events(self):
        if self._on_stream is not None:
            await self._on_stream()
        for event in self._events:
            yield event


def response_stream_events(response_id: str) -> list[object]:
    response = SimpleNamespace(id=response_id, usage=None)
    return [
        SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(type="response.created", response=response),
        ),
        SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(type="response.completed", response=response),
        ),
    ]


class NativeAgentLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        agent_observability.reset_agent_observability_for_tests()
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

    def tearDown(self) -> None:
        mlflow.flush_trace_async_logging(terminate=True)
        agent_observability.reset_agent_observability_for_tests()

    def create_durable_run(
        self,
        *,
        status: AgentRunStatus = AgentRunStatus.queued,
    ) -> str:
        with self.Session() as db:
            user = User(email="durable-run@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            skill = AgentSkill(
                owner_user_id=user.id,
                slug="durable-run-skill",
                name="持久化测试 Skill",
                description="测试持久化执行。",
                draft_instructions="# 方法\n需要时调用 generate_image。",
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
                content_hash="sha256:durable-run",
                published_by_user_id=user.id,
            )
            db.add(version)
            db.flush()
            skill.active_version_id = version.id
            conversation = NativeAgentConversation(
                owner_user_id=user.id,
                title="持久化测试",
            )
            db.add(conversation)
            db.flush()
            run = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=version.id,
                status=status,
                model_snapshot="test-model",
                skill_name_snapshot=version.name_snapshot,
                skill_version_snapshot=1,
                skill_content_hash_snapshot=version.content_hash,
                style_name_snapshot="测试风格",
                style_prompt_snapshot="测试风格提示词",
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
                    payload_json='{"content":"生成图片"}',
                )
            )
            db.commit()
            return run.id

    def test_generate_image_is_real_function_tool_and_returns_image_to_model(self) -> None:
        recorded_prompts: list[str] = []
        lifecycle: list[str] = []

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

        class FakeStore:
            def prepare_tool(inner_self, *, tool_call_id, prompt):
                self.assertEqual("call-1", tool_call_id)
                self.assertEqual("完整的图片提示词", prompt)
                lifecycle.append("prepared")
                return SimpleNamespace(id="step-1")

            def start_tool(inner_self, step_id):
                self.assertEqual("step-1", step_id)
                lifecycle.append("running")

            def complete_tool(inner_self, step_id, **kwargs):
                self.assertEqual("step-1", step_id)
                self.assertEqual("完整的图片提示词", kwargs["prompt"])
                lifecycle.append("succeeded")
                return CompletedNativeTool(
                    step_id=step_id,
                    image_id="image-1",
                    asset_id="asset-1",
                    storage_backend=StorageBackend.local,
                    storage_key="unused.png",
                    public_url="data:image/png;base64,aW1hZ2U=",
                    content_type="image/png",
                    width=1024,
                    height=1792,
                    provider_request_id="provider-request",
                )

            def fail_tool(inner_self, step_id, exc):
                raise AssertionError((step_id, exc))

            def append_event(inner_self, event_type, payload):
                raise AssertionError((event_type, payload))

        tool = build_generate_image_tool(
            NativeImageToolContext(
                run_id="run-1",
                image_model="gpt-image-2",
                aspect_ratio="9:16",
                reference_urls=(),
            ),
            image_generator=fake_image_generator,
            store=FakeStore(),
        )

        self.assertEqual("generate_image", tool.name)
        self.assertIn("Runtime 不会在背后拼接或改写 Prompt", tool.description)
        self.assertNotIn("测试风格", tool.description)
        self.assertNotIn("粗线条暖色", tool.description)
        self.assertNotIn("gpt-image-2", tool.description)
        self.assertNotIn("9:16", tool.description)
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
        self.assertEqual(["prepared", "running", "succeeded"], lifecycle)
        self.assertIsInstance(output[0], ToolOutputText)
        self.assertIsInstance(output[1], ToolOutputImage)
        self.assertEqual("data:image/png;base64,aW1hZ2U=", output[1].image_url)

    def test_generate_speech_is_real_function_tool_and_returns_asset_metadata(self) -> None:
        lifecycle: list[str] = []

        def fake_speech_generator(**kwargs):
            self.assertEqual("你好，这是语音测试。", kwargs["text"])
            return GeneratedSpeech(
                content=b"fake-mp3",
                content_type="audio/mpeg",
                response_format="mp3",
                sample_rate=24000,
                provider_request_id="speech-request",
                duration_ms=1500,
            )

        class FakeStore:
            def prepare_speech_tool(inner_self, *, tool_call_id, text):
                self.assertEqual("speech-call-1", tool_call_id)
                self.assertEqual("你好，这是语音测试。", text)
                lifecycle.append("prepared")
                return SimpleNamespace(id="speech-step-1")

            def start_tool(inner_self, step_id):
                self.assertEqual("speech-step-1", step_id)
                lifecycle.append("running")

            def complete_speech_tool(inner_self, step_id, **kwargs):
                self.assertEqual("speech-step-1", step_id)
                self.assertEqual("seed-tts-2.0", kwargs["resource_id"])
                self.assertEqual("seed-tts-2.0-standard", kwargs["model"])
                self.assertEqual(
                    "zh_female_xinlingjitang_uranus_bigtts",
                    kwargs["speaker"],
                )
                lifecycle.append("succeeded")
                return CompletedNativeSpeech(
                    step_id=step_id,
                    audio_id="audio-1",
                    asset_id="asset-1",
                    text=kwargs["text"],
                    content_type="audio/mpeg",
                    byte_size=8,
                    response_format="mp3",
                    sample_rate=24000,
                    duration_ms=1500,
                    provider_request_id="speech-request",
                )

            def fail_tool(inner_self, step_id, exc):
                raise AssertionError((step_id, exc))

            def append_event(inner_self, event_type, payload):
                raise AssertionError((event_type, payload))

        settings = native_agent_loop.Settings(
            doubao_voice_gen_resource_id="seed-tts-2.0",
            doubao_voice_gen_model="seed-tts-2.0-standard",
            doubao_voice_gen_speaker=(
                "zh_female_xinlingjitang_uranus_bigtts"
            ),
        )
        tool = build_generate_speech_tool(
            "run-1",
            settings=settings,
            speech_generator=fake_speech_generator,
            store=FakeStore(),
        )

        self.assertEqual("generate_speech", tool.name)
        self.assertIn("seed-tts-2.0-standard", tool.description)
        self.assertIn(
            "zh_female_xinlingjitang_uranus_bigtts",
            tool.description,
        )
        output = asyncio.run(
            tool.on_invoke_tool(
                ToolContext(
                    context=None,
                    tool_name="generate_speech",
                    tool_call_id="speech-call-1",
                    tool_arguments='{"text":"你好，这是语音测试。"}',
                ),
                json.dumps({"text": "你好，这是语音测试。"}),
            )
        )

        self.assertEqual(["prepared", "running", "succeeded"], lifecycle)
        self.assertEqual(1, len(output))
        self.assertIsInstance(output[0], ToolOutputText)
        payload = json.loads(output[0].text)
        self.assertEqual("audio-1", payload["audio_id"])
        self.assertEqual("asset-1", payload["asset_id"])
        self.assertEqual(24000, payload["sample_rate"])

    def test_native_runtime_tools_follow_published_skill_version(self) -> None:
        self.assertEqual(
            ["generate_speech"],
            native_runtime_tool_names(
                '["generate_speech","inspect_image"]'
            ),
        )
        self.assertEqual(
            ["generate_image", "generate_speech"],
            native_runtime_tool_names(
                '["generate_image","generate_speech"]'
            ),
        )
        self.assertNotIn(
            "generate_speech",
            native_runtime_tool_names('["generate_image"]'),
        )

    def test_generate_speech_persists_audio_and_owner_can_read_asset(self) -> None:
        run_id = self.create_durable_run()
        provider_calls = 0

        def fake_speech_generator(**kwargs):
            nonlocal provider_calls
            provider_calls += 1
            self.assertEqual("持久化语音测试。", kwargs["text"])
            return GeneratedSpeech(
                content=b"persisted-mp3",
                content_type="audio/mpeg",
                response_format="mp3",
                sample_rate=24000,
                provider_request_id="persisted-request",
                duration_ms=1800,
            )

        settings = native_agent_loop.Settings(
            doubao_voice_gen_resource_id="seed-tts-2.0",
            doubao_voice_gen_model="seed-tts-2.0-standard",
            doubao_voice_gen_speaker=(
                "zh_female_xinlingjitang_uranus_bigtts"
            ),
        )
        tool = build_generate_speech_tool(
            run_id,
            settings=settings,
            speech_generator=fake_speech_generator,
            store=NativeAgentStore(run_id, session_factory=self.Session),
        )
        stored = StoredFile(
            storage_backend=StorageBackend.local,
            storage_key="generated_audio/native-test.mp3",
            byte_size=13,
            checksum_sha256="d" * 64,
        )

        with patch(
            "app.services.native_agent_persistence.save_binary_file",
            return_value=stored,
        ) as save_file:
            invocation_context = ToolContext(
                context=None,
                tool_name="generate_speech",
                tool_call_id="persisted-speech-call",
                tool_arguments='{"text":"持久化语音测试。"}',
            )
            output = asyncio.run(
                tool.on_invoke_tool(
                    invocation_context,
                    json.dumps({"text": "持久化语音测试。"}),
                )
            )
            replayed = asyncio.run(
                tool.on_invoke_tool(
                    invocation_context,
                    json.dumps({"text": "持久化语音测试。"}),
                )
            )

        self.assertEqual(1, provider_calls)
        save_file.assert_called_once_with(
            "generated_audio",
            b"persisted-mp3",
            ".mp3",
        )
        result = json.loads(output[0].text)
        self.assertEqual(result, json.loads(replayed[0].text))
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            audio = db.get(NativeAgentAudio, result["audio_id"])
            asset = db.get(FileAsset, result["asset_id"])
            owner = run.conversation.owner
            other = User(email="other-audio@example.com", password_hash="hash")
            db.add(other)
            db.flush()

            self.assertEqual(1, run.speech_call_count)
            self.assertEqual(audio.asset_id, asset.id)
            self.assertEqual("持久化语音测试。", audio.text)
            self.assertEqual("seed-tts-2.0-standard", audio.model_snapshot)
            self.assertEqual("audio/mpeg", asset.content_type)
            self.assertTrue(can_read_asset(asset, owner, db))
            self.assertFalse(can_read_asset(asset, other, db))

    def test_render_story_video_persists_video_and_reuses_tool_call(self) -> None:
        run_id = self.create_durable_run()
        renderer_calls = 0
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "panel.png"
            audio_path = root / "narration.mp3"
            image_path.write_bytes(b"png")
            audio_path.write_bytes(b"mp3")
            resolved_scene = RemotionScene(
                scene_id="001",
                image_path=image_path,
                audio_path=audio_path,
                subtitle="故事开始了。",
                duration_ms=2100,
                motion_preset="zoom_in",
            )

            def fake_renderer(**kwargs):
                nonlocal renderer_calls
                renderer_calls += 1
                self.assertEqual([resolved_scene], kwargs["scenes"])
                self.assertIsNone(kwargs["bgm_path"])
                return GeneratedRemotionVideo(
                    content=b"persisted-mp4",
                    content_type="video/mp4",
                    template_id="narrated-panel-v1",
                    renderer_version="4.0.499",
                    duration_ms=2100,
                    duration_in_frames=63,
                    fps=30,
                    width=1080,
                    height=1920,
                )

            tool = build_render_story_video_tool(
                run_id,
                settings=native_agent_loop.Settings(),
                video_renderer=fake_renderer,
                store=NativeAgentStore(
                    run_id,
                    session_factory=self.Session,
                ),
            )
            stored = StoredFile(
                storage_backend=StorageBackend.local,
                storage_key="generated_video/native-test.mp4",
                byte_size=13,
                checksum_sha256="e" * 64,
            )
            arguments = {
                "scenes": [
                    {
                        "image_id": "image-1",
                        "audio_id": "audio-1",
                        "subtitle": "故事开始了。",
                        "motion_preset": "zoom_in",
                    }
                ]
            }
            invocation_context = ToolContext(
                context=None,
                tool_name="render_story_video",
                tool_call_id="persisted-video-call",
                tool_arguments=json.dumps(arguments, ensure_ascii=False),
            )
            snapshots = [
                {
                    "scene_order": 1,
                    "image_id": "image-1",
                    "audio_id": "audio-1",
                    "subtitle": "故事开始了。",
                    "duration_ms": 2100,
                    "motion_preset": "zoom_in",
                }
            ]
            with (
                patch(
                    "app.services.native_agent_loop._resolve_video_inputs",
                    return_value=([resolved_scene], snapshots, None),
                ),
                patch(
                    "app.services.native_agent_persistence.save_binary_file",
                    return_value=stored,
                ) as save_file,
            ):
                output = asyncio.run(
                    tool.on_invoke_tool(
                        invocation_context,
                        json.dumps(arguments, ensure_ascii=False),
                    )
                )
                replayed = asyncio.run(
                    tool.on_invoke_tool(
                        invocation_context,
                        json.dumps(arguments, ensure_ascii=False),
                    )
                )

        self.assertEqual(1, renderer_calls)
        save_file.assert_called_once_with(
            "generated_video",
            b"persisted-mp4",
            ".mp4",
        )
        result = json.loads(output[0].text)
        self.assertEqual(result, json.loads(replayed[0].text))
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            video = db.get(NativeAgentVideo, result["video_id"])
            asset = db.get(FileAsset, result["asset_id"])
            owner = run.conversation.owner
            other = User(email="other-video@example.com", password_hash="hash")
            db.add(other)
            db.flush()

            self.assertEqual(1, run.video_call_count)
            self.assertEqual("narrated-panel-v1", video.template_id_snapshot)
            self.assertEqual(2100, video.duration_ms)
            self.assertEqual("video/mp4", asset.content_type)
            self.assertTrue(can_read_asset(asset, owner, db))
            self.assertFalse(can_read_asset(asset, other, db))

    def test_generate_image_requires_style_but_has_no_hidden_default(self) -> None:
        def fail_generator(**kwargs):
            del kwargs
            raise AssertionError("无 Style 时不应调用 Provider")

        tool = build_generate_image_tool(
            NativeImageToolContext(
                run_id="run-2",
                image_model=None,
                aspect_ratio=None,
                reference_urls=(),
            ),
            image_generator=fail_generator,
            store=SimpleNamespace(),
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

    def test_image_provider_failure_returns_tool_output_to_model(self) -> None:
        run_id = self.create_durable_run()

        def rejected_image_generator(**kwargs):
            del kwargs
            raise ImageProviderResponseError(
                "图片 Provider 请求失败：HTTP 400 安全政策拦截"
            )

        tool = build_generate_image_tool(
            NativeImageToolContext(
                run_id=run_id,
                image_model="gpt-image-2",
                aspect_ratio="9:16",
                reference_urls=(),
            ),
            image_generator=rejected_image_generator,
            store=NativeAgentStore(run_id, session_factory=self.Session),
        )
        output = asyncio.run(
            tool.on_invoke_tool(
                ToolContext(
                    context=None,
                    tool_name="generate_image",
                    tool_call_id="rejected-tool-call",
                    tool_arguments='{"prompt":"被拒绝的图片提示词"}',
                ),
                json.dumps({"prompt": "被拒绝的图片提示词"}),
            )
        )

        failure = json.loads(output)
        self.assertEqual("failed", failure["status"])
        self.assertEqual("image_provider_error", failure["error_type"])
        self.assertIn("HTTP 400", failure["message"])
        with self.Session() as db:
            step = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.run_id == run_id,
                    NativeAgentStep.tool_call_id == "rejected-tool-call",
                )
            )
            self.assertEqual(NativeAgentStepStatus.failed, step.status)
            event_types = db.scalars(
                select(NativeAgentEvent.event_type).where(
                    NativeAgentEvent.run_id == run_id
                )
            ).all()
            self.assertIn("tool.failed", event_types)

    def test_style_context_is_scoped_to_image_generation_instructions(self) -> None:
        run_id = self.create_durable_run()
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            instructions = native_agent_instructions(run)

        self.assertIn("<image_generation_context>", instructions)
        self.assertIn('"style_name":"测试风格"', instructions)
        self.assertIn('"aspect_ratio":"9:16"', instructions)
        self.assertIn('"style_prompt":"测试风格提示词"', instructions)
        self.assertIn("只用于规划图片", instructions)

    def test_generate_image_idempotency_reuses_success_without_provider_call(self) -> None:
        run_id = self.create_durable_run()
        provider_calls = 0

        def image_generator(**kwargs):
            nonlocal provider_calls
            provider_calls += 1
            self.assertEqual("幂等图片提示词", kwargs["prompt"])
            return GeneratedImageFile(
                storage_backend=StorageBackend.local,
                storage_key="generated_image/idempotent.png",
                public_url="data:image/png;base64,aWRlbXBvdGVudA==",
                byte_size=10,
                checksum_sha256="c" * 64,
                content_type="image/png",
                original_filename="idempotent.png",
                provider_request_id="provider-idempotent",
                width=1024,
                height=1792,
            )

        tool = build_generate_image_tool(
            NativeImageToolContext(
                run_id=run_id,
                image_model="gpt-image-2",
                aspect_ratio="9:16",
                reference_urls=(),
            ),
            image_generator=image_generator,
            store=NativeAgentStore(run_id, session_factory=self.Session),
        )
        invocation_context = ToolContext(
            context=None,
            tool_name="generate_image",
            tool_call_id="stable-tool-call",
            tool_arguments='{"prompt":"幂等图片提示词"}',
        )
        first = asyncio.run(
            tool.on_invoke_tool(
                invocation_context,
                json.dumps({"prompt": "幂等图片提示词"}),
            )
        )
        second = asyncio.run(
            tool.on_invoke_tool(
                invocation_context,
                json.dumps({"prompt": "幂等图片提示词"}),
            )
        )

        self.assertEqual(1, provider_calls)
        self.assertEqual(first[1].image_url, second[1].image_url)
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            self.assertEqual(1, run.image_call_count)
            steps = db.scalars(
                select(NativeAgentStep).where(NativeAgentStep.run_id == run_id)
            ).all()
            self.assertEqual(1, len(steps))
            self.assertEqual(NativeAgentStepStatus.succeeded, steps[0].status)
            prepared_event = db.scalar(
                select(NativeAgentEvent).where(
                    NativeAgentEvent.run_id == run_id,
                    NativeAgentEvent.event_type == "tool.prepared",
                )
            )
            self.assertEqual(
                "幂等图片提示词",
                json.loads(prepared_event.payload_json)["arguments"]["prompt"],
            )

    def test_sdk_context_session_persists_and_finds_tool_output(self) -> None:
        run_id = self.create_durable_run()
        sdk_session = NativeAgentDatabaseSession(
            run_id,
            session_factory=self.Session,
        )
        asyncio.run(
            sdk_session.add_items(
                [
                    {"role": "user", "content": "生成图片"},
                    {
                        "type": "function_call_output",
                        "call_id": "call-persisted",
                        "output": "done",
                    },
                ]
            )
        )

        self.assertTrue(asyncio.run(sdk_session.has_items()))
        self.assertTrue(
            asyncio.run(sdk_session.has_tool_output("call-persisted"))
        )
        self.assertFalse(
            asyncio.run(sdk_session.has_tool_output("call-missing"))
        )
        with self.Session() as db:
            self.assertEqual(
                2,
                db.query(NativeAgentContextItem)
                .filter(NativeAgentContextItem.run_id == run_id)
                .count(),
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
                draft_tool_names_json='["generate_image","inspect_image"]',
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

        def fake_run(
            agent,
            input_value,
            *,
            run_config,
            max_turns,
            session,
        ):
            captured["agent"] = agent
            captured["input"] = input_value
            captured["run_config"] = run_config
            captured["max_turns"] = max_turns
            captured["session"] = session
            return FakeStreamedResult(
                final_output="已完成纯文本回答",
                raw_response_count=1,
                events=[
                    response_stream_events("response-text")[0],
                    SimpleNamespace(
                        type="raw_response_event",
                        data=SimpleNamespace(
                            type="response.output_text.delta",
                            delta="正在整理结果",
                        ),
                    ),
                    SimpleNamespace(
                        type="raw_response_event",
                        data=SimpleNamespace(
                            type="response.output_item.added",
                            output_index=1,
                            item=SimpleNamespace(
                                id="function-item-1",
                                type="function_call",
                                call_id="function-call-1",
                                name="generate_image",
                            ),
                        ),
                    ),
                    SimpleNamespace(
                        type="raw_response_event",
                        data=SimpleNamespace(
                            type="response.function_call_arguments.delta",
                            item_id="function-item-1",
                            delta='{"prompt":"真实',
                        ),
                    ),
                    SimpleNamespace(
                        type="raw_response_event",
                        data=SimpleNamespace(
                            type="response.function_call_arguments.done",
                            item_id="function-item-1",
                            name="generate_image",
                            arguments='{"prompt":"真实参数"}',
                        ),
                    ),
                    response_stream_events("response-text")[1],
                ],
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
            patch.object(
                native_agent_loop.Runner,
                "run_streamed",
                side_effect=fake_run,
            ),
        ):
            asyncio.run(execute_native_agent_run(run_id, settings=settings))

        agent = captured["agent"]
        self.assertEqual(["generate_image"], [tool.name for tool in agent.tools])
        self.assertEqual("只回答，不要生图", captured["input"])
        self.assertEqual(12, captured["max_turns"])
        self.assertEqual(
            2,
            captured["run_config"].tool_execution.max_function_tool_concurrency,
        )
        with self.Session() as db:
            persisted = db.scalar(
                select(NativeAgentRun).where(NativeAgentRun.id == run_id)
            )
            self.assertEqual(AgentRunStatus.succeeded, persisted.status)
            self.assertEqual(0, persisted.image_call_count)
            self.assertEqual("已完成纯文本回答", persisted.final_output)
            steps = db.scalars(
                select(NativeAgentStep)
                .where(NativeAgentStep.run_id == run_id)
                .order_by(NativeAgentStep.sequence.asc())
            ).all()
            self.assertEqual(
                [NativeAgentStepType.model_call, NativeAgentStepType.final],
                [step.step_type for step in steps],
            )
            self.assertTrue(
                all(step.status == NativeAgentStepStatus.succeeded for step in steps)
            )
            events = db.scalars(
                select(NativeAgentEvent)
                .where(NativeAgentEvent.run_id == run_id)
                .order_by(NativeAgentEvent.sequence.asc())
            ).all()
            event_types = [event.event_type for event in events]
            self.assertIn("response.output_text.delta", event_types)
            self.assertIn("response.function_call.started", event_types)
            self.assertIn("response.function_call.arguments.delta", event_types)
            self.assertIn("response.function_call.arguments.done", event_types)
            arguments_event = next(
                event
                for event in events
                if event.event_type == "response.function_call.arguments.done"
            )
            self.assertEqual(
                '{"prompt":"真实参数"}',
                json.loads(arguments_event.payload_json)["arguments"],
            )
            self.assertEqual("run.completed", events[-1].event_type)

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
                draft_tool_names_json='["generate_image","inspect_image"]',
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
                "app.api.native_agent.enqueue_native_agent_run",
                new=AsyncMock(),
            ) as enqueue:
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

            enqueue.assert_awaited_once()
            self.assertEqual(response.data.id, enqueue.await_args.args[0])
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
            public_url="data:image/png;base64,dHJhY2U=",
            byte_size=10,
            checksum_sha256="b" * 64,
            content_type="image/png",
            original_filename="native-trace.png",
            provider_request_id="provider-native-trace",
            width=1024,
            height=1792,
        )

        def fake_run(
            agent,
            input_value,
            *,
            run_config,
            max_turns,
            session,
        ):
            del input_value, run_config, max_turns, session

            async def invoke_tool():
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

            return FakeStreamedResult(
                final_output="private native final output",
                raw_response_count=2,
                events=[
                    *response_stream_events("response-trace-1"),
                    *response_stream_events("response-trace-2"),
                ],
                on_stream=invoke_tool,
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
                    "run_streamed",
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
            tool_span = next(
                span for span in spans if span.name == "native_agent.generate_image"
            )
            provider_span = next(
                span for span in spans if span.name == "native_agent.image_provider"
            )
            self.assertEqual("succeeded", root_span.attributes["run_status"])
            self.assertEqual(2, root_span.attributes["model_call_count"])
            self.assertEqual(1, root_span.attributes["image_call_count"])
            self.assertEqual("TOOL", tool_span.span_type)
            self.assertEqual(SpanStatusCode.OK, tool_span.status.status_code)
            self.assertEqual("succeeded", tool_span.attributes["result_status"])
            self.assertEqual("TASK", provider_span.span_type)
            self.assertEqual(SpanStatusCode.OK, provider_span.status.status_code)
            serialized = json.dumps(traces[0].to_dict())
            self.assertNotIn("private native user content", serialized)
            self.assertNotIn("private image prompt", serialized)
            self.assertNotIn("private native final output", serialized)
            self.assertNotIn("private style instructions", serialized)
            self.assertNotIn("private.example", serialized)
            self.assertNotIn("private-primary-secret", serialized)

    def test_recovery_requeues_interrupted_model_run_and_existing_queued_run(self) -> None:
        with self.Session() as db:
            user = User(email="native-recovery@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            skill = AgentSkill(
                owner_user_id=user.id,
                slug="native-recovery-skill",
                name="恢复测试 Skill",
                description="恢复测试。",
                draft_instructions="# 方法",
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
                content_hash="sha256:native-recovery",
                published_by_user_id=user.id,
            )
            db.add(version)
            db.flush()
            skill.active_version_id = version.id
            conversation = NativeAgentConversation(
                owner_user_id=user.id,
                title="恢复测试",
            )
            db.add(conversation)
            db.flush()
            interrupted = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=version.id,
                status=AgentRunStatus.running,
                model_snapshot="test-model",
                skill_name_snapshot=version.name_snapshot,
                skill_version_snapshot=1,
                skill_content_hash_snapshot=version.content_hash,
            )
            queued = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=version.id,
                status=AgentRunStatus.queued,
                model_snapshot="test-model",
                skill_name_snapshot=version.name_snapshot,
                skill_version_snapshot=1,
                skill_content_hash_snapshot=version.content_hash,
            )
            db.add_all([interrupted, queued])
            db.commit()
            interrupted_id = interrupted.id
            queued_id = queued.id

        async def recover() -> AsyncMock:
            enqueue = AsyncMock()
            with (
                patch.object(native_agent_worker, "SessionLocal", self.Session),
                patch.object(native_agent_worker, "_queue", asyncio.Queue()),
                patch.object(
                    native_agent_worker,
                    "enqueue_native_agent_run",
                    enqueue,
                ),
            ):
                await native_agent_worker.recover_native_agent_runs()
            return enqueue

        enqueue = asyncio.run(recover())
        self.assertEqual(
            [interrupted_id, queued_id],
            [call.args[0] for call in enqueue.await_args_list],
        )
        with self.Session() as db:
            persisted = db.get(NativeAgentRun, interrupted_id)
            self.assertEqual(AgentRunStatus.queued, persisted.status)
            self.assertIsNone(persisted.error_code)

    def test_recovery_marks_inflight_tool_unknown_and_does_not_replay(self) -> None:
        run_id = self.create_durable_run(status=AgentRunStatus.running)
        with self.Session() as db:
            db.add(
                NativeAgentStep(
                    run_id=run_id,
                    sequence=1,
                    step_type=NativeAgentStepType.tool_call,
                    status=NativeAgentStepStatus.running,
                    name="generate_image",
                    tool_call_id="ambiguous-tool-call",
                    idempotency_key=(
                        f"native:{run_id}:generate_image:ambiguous-tool-call"
                    ),
                    attempts=1,
                    started_at=datetime.utcnow(),
                )
            )
            db.commit()

        enqueue = AsyncMock()

        async def recover() -> None:
            with (
                patch.object(native_agent_worker, "SessionLocal", self.Session),
                patch.object(native_agent_worker, "_queue", asyncio.Queue()),
                patch.object(
                    native_agent_worker,
                    "enqueue_native_agent_run",
                    enqueue,
                ),
            ):
                await native_agent_worker.recover_native_agent_runs()

        asyncio.run(recover())

        enqueue.assert_not_awaited()
        with self.Session() as db:
            run = db.get(NativeAgentRun, run_id)
            step = db.scalar(
                select(NativeAgentStep).where(NativeAgentStep.run_id == run_id)
            )
            self.assertEqual(AgentRunStatus.failed, run.status)
            self.assertEqual("NativeAgentRecoveryBlocked", run.error_code)
            self.assertEqual(NativeAgentStepStatus.unknown, step.status)

    def test_native_worker_executes_enqueued_run_id(self) -> None:
        async def exercise_worker() -> AsyncMock:
            execute = AsyncMock()
            with patch.object(
                native_agent_worker,
                "execute_native_agent_run",
                execute,
            ):
                native_agent_worker.init_native_agent_queue()
                try:
                    await native_agent_worker.enqueue_native_agent_run("run-queued")
                    await native_agent_worker._queue.join()
                finally:
                    await native_agent_worker.shutdown_native_agent_queue()
            return execute

        execute = asyncio.run(exercise_worker())
        execute.assert_awaited_once_with("run-queued")

    def test_run_sse_streams_incremental_owned_snapshot_until_terminal(self) -> None:
        with self.Session() as db:
            user = User(email="native-sse@example.com", password_hash="hash")
            other = User(email="native-sse-other@example.com", password_hash="hash")
            db.add_all([user, other])
            db.flush()
            skill = AgentSkill(
                owner_user_id=user.id,
                slug="native-sse-skill",
                name="SSE 测试 Skill",
                description="SSE 测试。",
                draft_instructions="# 方法",
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
                content_hash="sha256:native-sse",
                published_by_user_id=user.id,
            )
            db.add(version)
            db.flush()
            skill.active_version_id = version.id
            conversation = NativeAgentConversation(
                owner_user_id=user.id,
                title="SSE 测试",
            )
            db.add(conversation)
            db.flush()
            run = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=version.id,
                status=AgentRunStatus.running,
                model_snapshot="test-model",
                skill_name_snapshot=version.name_snapshot,
                skill_version_snapshot=1,
                skill_content_hash_snapshot=version.content_hash,
            )
            db.add(run)
            db.flush()
            db.add(
                NativeAgentItem(
                    run_id=run.id,
                    sequence=1,
                    item_type=NativeAgentItemType.user_input,
                    payload_json='{"content":"测试 SSE"}',
                )
            )
            db.commit()
            run_id = run.id

            request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
            with patch("app.api.native_agent.SessionLocal", self.Session):
                response = asyncio.run(
                    stream_native_agent_run_events(run_id, request, user, db)
                )

                async def consume() -> list[str]:
                    iterator = response.body_iterator.__aiter__()
                    first = await anext(iterator)
                    with self.Session() as update_db:
                        persisted = update_db.get(NativeAgentRun, run_id)
                        persisted.status = AgentRunStatus.succeeded
                        persisted.final_output = "已完成"
                        persisted.finished_at = datetime.utcnow()
                        update_db.add(
                            NativeAgentItem(
                                run_id=run_id,
                                sequence=2,
                                item_type=NativeAgentItemType.assistant_output,
                                payload_json='{"content":"已完成"}',
                            )
                        )
                        update_db.add(
                            NativeAgentEvent(
                                run_id=run_id,
                                sequence=1,
                                event_type="run.completed",
                                payload_json='{"status":"succeeded"}',
                            )
                        )
                        update_db.commit()
                    second = await anext(iterator)
                    third = await anext(iterator)
                    with self.assertRaises(StopAsyncIteration):
                        await anext(iterator)
                    return [
                        chunk.decode() if isinstance(chunk, bytes) else chunk
                        for chunk in (first, second, third)
                    ]

                frames = asyncio.run(consume())

            self.assertEqual(3, len(frames))
            self.assertIn("event: run.updated", frames[0])
            self.assertIn('"status":"running"', frames[0])
            self.assertIn("id: 1", frames[1])
            self.assertIn("event: native.event", frames[1])
            self.assertIn('"status":"succeeded"', frames[2])
            self.assertIn('"content":"已完成"', frames[2])
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    stream_native_agent_run_events(run_id, request, other, db)
                )
            self.assertEqual(404, raised.exception.status_code)
