import asyncio
from datetime import datetime, timedelta
import json
import unittest

from agents import ToolOutputText
from agents.tool_context import ToolContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    NativeAgentConversation,
    NativeAgentRun,
    User,
    YoutubeChannel,
    YoutubeChannelBenchmark,
    YoutubeUploadedVideo,
)
from app.models.enums import AgentRunStatus, AgentSkillStatus, UserRole
from app.services.account_creation_context import (
    AccountCreationContextForbidden,
    get_account_creation_context,
)
from app.services.native_agent_loop import (
    build_get_account_creation_context_tool,
)


class AccountCreationContextTests(unittest.TestCase):
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

    def create_run(self, *, role: UserRole = UserRole.admin) -> str:
        with self.Session() as db:
            user = User(
                email=f"{role.value}-{id(self)}@example.com",
                password_hash="hash",
                role=role,
            )
            db.add(user)
            db.flush()
            skill = AgentSkill(
                owner_user_id=user.id,
                slug=f"account-context-{role.value}-{id(self)}",
                name="账号上下文测试",
                description="读取账号上下文。",
                draft_instructions="# 方法\n读取账号上下文。",
                draft_tool_names_json='["get_account_creation_context"]',
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
                content_hash=f"sha256:{role.value}-{id(self)}",
                published_by_user_id=user.id,
            )
            db.add(version)
            db.flush()
            skill.active_version_id = version.id
            conversation = NativeAgentConversation(
                owner_user_id=user.id,
                title="账号上下文测试",
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
            )
            db.add(run)
            db.commit()
            return run.id

    def create_channel(
        self,
        *,
        alias: str = "历史商业取证",
        title: str = "Averyryz Wilson",
        handle: str = "AveryryzWilson",
        channel_id: str = "UC-history-business",
    ) -> str:
        with self.Session() as db:
            channel = YoutubeChannel(
                channel_id=channel_id,
                title=title,
                handle=handle,
                remote_status="normal",
                alias=alias,
                account_email="must-not-leak@example.com",
                account_positioning="用商业证据重新解释历史事件。",
                target_audience="关注商业与历史的中文读者。",
                stage_goal="验证三个稳定选题方向。",
                ai_definition="理性、克制的商业史研究员。",
                operation_notes="结论必须有证据链。",
                total_subscribers=1200,
                total_views=34567,
                total_watch_time_hours=456.5,
                total_videos=12,
                analytics_json='{"private_raw_metric":"must-not-leak"}',
                remote_last_sync_at=datetime(2026, 7, 29, 8, 0),
                last_sync_success_at=datetime(2026, 7, 29, 8, 0),
            )
            db.add(channel)
            db.flush()
            db.add(
                YoutubeChannelBenchmark(
                    channel_id=channel.id,
                    platform="youtube",
                    name="商业史对标",
                    platform_account_id="@business-history",
                    profile_url="https://youtube.com/@business-history",
                    notes="以证据切入，先提出反常识问题。",
                )
            )
            base_time = datetime(2026, 7, 1, 9, 0)
            for index in range(12):
                db.add(
                    YoutubeUploadedVideo(
                        channel_id=channel.id,
                        youtube_video_id=f"{channel_id}-video-{index}",
                        title=f"历史商业样本 {index}",
                        description=(
                            "长描述" * 1100 if index == 11 else f"说明 {index}"
                        ),
                        tags_json=json.dumps(
                            [f"标签-{tag}" for tag in range(25)],
                            ensure_ascii=False,
                        ),
                        visibility="public",
                        views=index * 100,
                        likes=index * 10,
                        uploaded_at=base_time + timedelta(days=index),
                    )
                )
            db.commit()
            return channel.id

    def test_exact_alias_returns_bounded_creation_context_without_secrets(
        self,
    ) -> None:
        run_id = self.create_run()
        channel_id = self.create_channel()

        payload = get_account_creation_context(
            " 历史商业取证 ",
            run_id=run_id,
            session_factory=self.Session,
        )

        self.assertEqual("resolved", payload["status"])
        self.assertEqual("alias", payload["matched_by"])
        self.assertEqual(channel_id, payload["account"]["account_id"])
        self.assertEqual(
            "用商业证据重新解释历史事件。",
            payload["content_strategy"]["account_positioning"],
        )
        self.assertEqual(1, len(payload["benchmarks"]))
        self.assertEqual(10, len(payload["recent_videos"]))
        self.assertEqual(
            "UC-history-business-video-11",
            payload["recent_videos"][0]["youtube_video_id"],
        )
        self.assertTrue(payload["recent_videos"][0]["description_truncated"])
        self.assertEqual(20, len(payload["recent_videos"][0]["tags"]))
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("must-not-leak@example.com", serialized)
        self.assertNotIn("private_raw_metric", serialized)

    def test_handle_match_accepts_at_prefix(self) -> None:
        run_id = self.create_run()
        self.create_channel()

        payload = get_account_creation_context(
            "@averyryzwilson",
            run_id=run_id,
            session_factory=self.Session,
        )

        self.assertEqual("resolved", payload["status"])
        self.assertEqual("handle", payload["matched_by"])

    def test_partial_match_returns_candidates_without_strategy(self) -> None:
        run_id = self.create_run()
        self.create_channel()

        payload = get_account_creation_context(
            "历史商业",
            run_id=run_id,
            session_factory=self.Session,
        )

        self.assertEqual("needs_confirmation", payload["status"])
        self.assertEqual("partial_matches_only", payload["reason"])
        self.assertEqual("历史商业取证", payload["candidates"][0]["alias"])
        self.assertNotIn("content_strategy", payload)

    def test_duplicate_exact_alias_requires_confirmation(self) -> None:
        run_id = self.create_run()
        self.create_channel()
        self.create_channel(
            title="Second Channel",
            handle="SecondChannel",
            channel_id="UC-second-history-business",
        )

        payload = get_account_creation_context(
            "历史商业取证",
            run_id=run_id,
            session_factory=self.Session,
        )

        self.assertEqual("needs_confirmation", payload["status"])
        self.assertEqual("multiple_exact_matches", payload["reason"])
        self.assertEqual(2, len(payload["candidates"]))
        self.assertNotIn("content_strategy", payload)

    def test_non_admin_run_cannot_read_shared_account_context(self) -> None:
        run_id = self.create_run(role=UserRole.user)
        self.create_channel()

        with self.assertRaises(AccountCreationContextForbidden):
            get_account_creation_context(
                "历史商业取证",
                run_id=run_id,
                session_factory=self.Session,
            )

    def test_native_tool_returns_json_payload_to_model(self) -> None:
        run_id = self.create_run()
        self.create_channel()
        tool = build_get_account_creation_context_tool(
            run_id,
            session_factory=self.Session,
        )
        arguments = '{"account_name":"历史商业取证"}'

        output = asyncio.run(
            tool.on_invoke_tool(
                ToolContext(
                    context=None,
                    tool_name="get_account_creation_context",
                    tool_call_id="account-context-1",
                    tool_arguments=arguments,
                ),
                arguments,
            )
        )

        self.assertEqual(1, len(output))
        self.assertIsInstance(output[0], ToolOutputText)
        self.assertEqual("resolved", json.loads(output[0].text)["status"])


if __name__ == "__main__":
    unittest.main()
