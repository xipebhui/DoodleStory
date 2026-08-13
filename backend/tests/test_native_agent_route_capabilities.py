import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.native_agent import create_native_agent_run
from app.core.config import Settings
from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    DurableAgentWorkflow,
    FileAsset,
    NativeAgentConversation,
    NativeAgentImage,
    NativeAgentItem,
    NativeAgentRun,
    NativeAgentStep,
    Style,
    User,
)
from app.models.enums import (
    AgentRunStatus,
    AgentSkillStatus,
    FileAssetPurpose,
    NativeAgentStepStatus,
    NativeAgentStepType,
    StyleReferenceMode,
    StyleStatus,
    StorageBackend,
    UserRole,
)
from app.schemas.native_agent import NativeAgentRunCreate
from app.services.native_agent_model_routes import (
    NativeAgentModelRouteSnapshot,
    SILICONFLOW_CHAT_ROUTE,
)
from app.services.native_agent_persistence import NativeAgentStore
from app.services.native_agent_persistence import CompletedNativeTool
from app.services import native_agent_loop
from app.services.native_agent_route_capabilities import (
    NativeAgentRouteCapabilityError,
    validate_native_agent_route_capability,
)


def route_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "session_secret": "route-capability-secret",
        "text_fallback_api_key": "huomiao-secret",
        "text_fallback_base_url": "https://huomiao.invalid/v1",
        "native_agent_default_route": "huomiao_responses",
        "native_agent_huomiao_model": "gpt-5.5",
        "siliconflow_api_key": "siliconflow-secret",
        "siliconflow_base_url": "https://api.siliconflow.invalid/v1",
        "native_agent_siliconflow_model": "deepseek-ai/DeepSeek-V3.2",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class NativeAgentRouteCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        with self.Session() as db:
            self.admin = User(
                email="admin-route@example.com",
                password_hash="hash",
                role=UserRole.admin,
            )
            self.user = User(email="user-route@example.com", password_hash="hash")
            db.add_all([self.admin, self.user])
            db.flush()
            self.style = Style(
                name="S03 离线风格",
                status=StyleStatus.active,
                image_model_name="grok-imagine-image",
                aspect_ratio="16:9",
                style_reference_mode=StyleReferenceMode.prompt,
                style_prompt="考古证据插画",
            )
            db.add(self.style)
            db.flush()
            self.exact_version = self._skill_version(
                db,
                slug="s03-exact",
                tools='["generate_image","inspect_image"]',
            )
            self.extra_version = self._skill_version(
                db,
                slug="s03-extra",
                tools='["generate_image","inspect_image","generate_speech"]',
            )
            db.commit()
            for value in (
                self.admin,
                self.user,
                self.style,
                self.exact_version,
                self.extra_version,
            ):
                db.refresh(value)
                db.expunge(value)

    def _skill_version(self, db, *, slug: str, tools: str) -> AgentSkillVersion:
        skill = AgentSkill(
            owner_user_id=None,
            slug=slug,
            name=slug,
            description="S03 capability test",
            draft_instructions="生成一张图片并检查。",
            draft_tool_names_json=tools,
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
            tool_names_json=tools,
            content_hash=f"sha256:{slug}",
            published_by_user_id=self.admin.id,
        )
        db.add(version)
        db.flush()
        skill.active_version_id = version.id
        return version

    def _conversation(self, db, user: User) -> NativeAgentConversation:
        conversation = NativeAgentConversation(owner_user_id=user.id, title="路由能力")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    @staticmethod
    def _counts(db) -> tuple[int, int, int]:
        return (
            db.query(NativeAgentRun).count(),
            db.query(NativeAgentItem).count(),
            db.query(DurableAgentWorkflow).count(),
        )

    def test_admin_explicit_route_persists_exact_snapshot(self) -> None:
        with self.Session() as db:
            conversation = self._conversation(db, self.admin)
            payload = NativeAgentRunCreate(
                content="执行 S03 单镜闭环",
                skill_version_id=self.exact_version.id,
                style_id=self.style.id,
                model_route=SILICONFLOW_CHAT_ROUTE,
            )
            with (
                patch("app.api.native_agent.get_settings", return_value=route_settings()),
                patch(
                    "app.api.native_agent.enqueue_native_agent_run",
                    new=AsyncMock(),
                ) as enqueue,
            ):
                response = asyncio.run(
                    create_native_agent_run(
                        conversation.id,
                        payload,
                        self.admin,
                        db,
                    )
                )
            enqueue.assert_awaited_once_with(response.data.id)
            self.assertEqual("siliconflow_chat_v1", response.data.model_route)
            self.assertEqual("siliconflow", response.data.model_provider)
            self.assertEqual("chat_completions", response.data.model_api_shape)
            self.assertEqual("deepseek-ai/DeepSeek-V3.2", response.data.model)

    def test_non_admin_and_invalid_profiles_write_nothing(self) -> None:
        cases = (
            (self.user, self.exact_version.id, self.style.id, route_settings(), 403),
            (self.admin, self.exact_version.id, None, route_settings(), 409),
            (self.admin, self.extra_version.id, self.style.id, route_settings(), 409),
            (
                self.admin,
                self.exact_version.id,
                self.style.id,
                route_settings(siliconflow_api_key=" "),
                503,
            ),
        )
        for user, version_id, style_id, settings, expected_status in cases:
            with self.subTest(status=expected_status, version=version_id):
                with self.Session() as db:
                    conversation = self._conversation(db, user)
                    before = self._counts(db)
                    payload = NativeAgentRunCreate(
                        content="越界请求",
                        skill_version_id=version_id,
                        style_id=style_id,
                        model_route=SILICONFLOW_CHAT_ROUTE,
                    )
                    with (
                        patch(
                            "app.api.native_agent.get_settings",
                            return_value=settings,
                        ),
                        patch(
                            "app.api.native_agent.enqueue_native_agent_run",
                            new=AsyncMock(),
                        ) as enqueue,
                    ):
                        with self.assertRaises(HTTPException) as caught:
                            asyncio.run(
                                create_native_agent_run(
                                    conversation.id,
                                    payload,
                                    user,
                                    db,
                                )
                            )
                    self.assertEqual(expected_status, caught.exception.status_code)
                    self.assertEqual(before, self._counts(db))
                    enqueue.assert_not_awaited()

    def test_publish_context_is_rejected_by_s03_profile(self) -> None:
        route = NativeAgentModelRouteSnapshot(
            route="siliconflow_chat_v1",
            provider="siliconflow",
            api_shape="chat_completions",
            model="deepseek-ai/DeepSeek-V3.2",
        )
        with self.assertRaisesRegex(
            NativeAgentRouteCapabilityError,
            "不允许携带",
        ):
            validate_native_agent_route_capability(
                route,
                selected_tool_names={"generate_image", "inspect_image"},
                style_id="style",
                creation_channel_id=None,
                youtube_channel_id="channel",
                youtube_publishable_video_id="video",
                has_youtube_publish_confirmation=True,
            )

    def test_image_attempt_budget_blocks_retry_before_provider_work(self) -> None:
        with self.Session() as db:
            conversation = self._conversation(db, self.admin)
            run = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=self.exact_version.id,
                style_id=self.style.id,
                status=AgentRunStatus.running,
                model_snapshot="deepseek-ai/DeepSeek-V3.2",
                model_route_snapshot="siliconflow_chat_v1",
                model_provider_snapshot="siliconflow",
                model_api_shape_snapshot="chat_completions",
                skill_name_snapshot=self.exact_version.name_snapshot,
                skill_version_snapshot=1,
                skill_content_hash_snapshot=self.exact_version.content_hash,
                style_reference_urls_json="[]",
            )
            db.add(run)
            db.flush()
            db.add(
                NativeAgentStep(
                    run_id=run.id,
                    sequence=1,
                    step_type=NativeAgentStepType.tool_call,
                    status=NativeAgentStepStatus.prepared,
                    name="generate_image",
                    tool_call_id="failed-call",
                    idempotency_key=f"native:{run.id}:generate_image:failed-call",
                    input_summary_json='{"prompt":"same","provider":"qy"}',
                    attempts=1,
                )
            )
            db.commit()
            run_id = run.id
        store = NativeAgentStore(run_id, session_factory=self.Session)
        with self.assertRaisesRegex(RuntimeError, "预算已用尽"):
            store.prepare_tool(
                tool_call_id="retry-call",
                prompt="same",
                provider="qy",
                max_provider_attempts=1,
            )

    def test_chat_image_tool_output_stays_text_only(self) -> None:
        completed = CompletedNativeTool(
            step_id="step",
            image_id="image",
            asset_id="asset",
            storage_backend="local",
            storage_key="image.png",
            public_url=None,
            content_type="image/png",
            width=1280,
            height=720,
            provider_request_id="provider-request",
        )
        with patch.object(native_agent_loop, "_completed_image_url") as image_url:
            outputs = asyncio.run(
                native_agent_loop._tool_outputs(completed, include_image=False)
            )
        image_url.assert_not_called()
        self.assertEqual(1, len(outputs))
        self.assertIn('"image_id": "image"', outputs[0].text)

    def test_completion_requires_real_inspection_for_the_only_image(self) -> None:
        with self.Session() as db:
            conversation = self._conversation(db, self.admin)
            run = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=self.exact_version.id,
                style_id=self.style.id,
                status=AgentRunStatus.running,
                model_snapshot="deepseek-ai/DeepSeek-V3.2",
                model_route_snapshot="siliconflow_chat_v1",
                model_provider_snapshot="siliconflow",
                model_api_shape_snapshot="chat_completions",
                skill_name_snapshot=self.exact_version.name_snapshot,
                skill_version_snapshot=1,
                skill_content_hash_snapshot=self.exact_version.content_hash,
                style_reference_urls_json="[]",
            )
            db.add(run)
            db.flush()
            asset = FileAsset(
                purpose=FileAssetPurpose.generated_image,
                storage_backend=StorageBackend.local,
                storage_key=f"offline/{run.id}.png",
                content_type="image/png",
                byte_size=1,
                width=1280,
                height=720,
            )
            db.add(asset)
            db.flush()
            image = NativeAgentImage(
                run_id=run.id,
                asset_id=asset.id,
                prompt="S03",
                image_model_snapshot="grok-imagine-image",
                aspect_ratio_snapshot="16:9",
                provider_snapshot="qy",
            )
            db.add(image)
            db.commit()
            run_id = run.id
            image_id = image.id
        store = NativeAgentStore(run_id, session_factory=self.Session)
        with self.assertRaisesRegex(RuntimeError, "缺少唯一"):
            store.validate_single_image_inspection_completion()

        with self.Session() as db:
            db.add(
                NativeAgentStep(
                    run_id=run_id,
                    sequence=1,
                    step_type=NativeAgentStepType.tool_call,
                    status=NativeAgentStepStatus.succeeded,
                    name="inspect_image",
                    tool_call_id="inspect-call",
                    idempotency_key=f"native:{run_id}:inspect_image:inspect-call",
                    output_ref_json=(
                        '{"image_id":"'
                        + image_id
                        + '","verdict":"accept","provider":"text_fallback",'
                        '"model":"Qwen/Qwen3-VL-32B-Instruct"}'
                    ),
                    attempts=1,
                )
            )
            db.commit()
        store.validate_single_image_inspection_completion()


if __name__ == "__main__":
    unittest.main()
