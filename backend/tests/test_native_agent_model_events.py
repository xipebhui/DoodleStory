import json
import unittest
from types import SimpleNamespace

from agents.models.fake_id import FAKE_RESPONSES_ID
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    NativeAgentConversation,
    NativeAgentEvent,
    NativeAgentRun,
    NativeAgentStep,
    User,
)
from app.models.enums import AgentRunStatus, AgentSkillStatus
from app.services.native_agent_model_events import (
    NativeModelEventAdapter,
    NativeModelEventAdapterError,
)
from app.services.native_agent_model_routes import NativeAgentModelRouteSnapshot
from app.services.native_agent_persistence import NativeAgentStore


class NativeAgentModelEventTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        with self.Session() as db:
            user = User(email="events@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            skill = AgentSkill(
                owner_user_id=user.id,
                slug="events",
                name="事件",
                description="事件适配测试",
                draft_instructions="测试",
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
                instructions="测试",
                tool_names_json=skill.draft_tool_names_json,
                content_hash="sha256:events",
                published_by_user_id=user.id,
            )
            db.add(version)
            db.flush()
            conversation = NativeAgentConversation(owner_user_id=user.id, title="事件")
            db.add(conversation)
            db.flush()
            run = NativeAgentRun(
                conversation_id=conversation.id,
                skill_version_id=version.id,
                status=AgentRunStatus.running,
                model_snapshot="deepseek-ai/DeepSeek-V3.2",
                model_route_snapshot="siliconflow_chat_v1",
                model_provider_snapshot="siliconflow",
                model_api_shape_snapshot="chat_completions",
                skill_name_snapshot=version.name_snapshot,
                skill_version_snapshot=1,
                skill_content_hash_snapshot=version.content_hash,
                style_reference_urls_json="[]",
            )
            db.add(run)
            db.commit()
            self.run_id = run.id
        self.store = NativeAgentStore(self.run_id, session_factory=self.Session)
        self.route = NativeAgentModelRouteSnapshot(
            route="siliconflow_chat_v1",
            provider="siliconflow",
            api_shape="chat_completions",
            model="deepseek-ai/DeepSeek-V3.2",
        )

    @staticmethod
    def _event(event_type: str, **values: object) -> SimpleNamespace:
        return SimpleNamespace(type=event_type, **values)

    def test_fake_ids_two_calls_and_duplicate_item_ids_remain_unambiguous(self) -> None:
        adapter = NativeModelEventAdapter(
            run_id=self.run_id,
            execution_attempt=2,
            route=self.route,
            store=self.store,
        )
        adapter.record_converted_message_count(4)
        adapter.handle(
            self._event(
                "response.created",
                response=SimpleNamespace(id=FAKE_RESPONSES_ID),
            )
        )
        for output_index, call_id, name, arguments in (
            (0, "call-a", "generate_image", '{"prompt":"a"}'),
            (1, "call-b", "inspect_image", '{"image_id":"img"}'),
        ):
            item = SimpleNamespace(
                id=FAKE_RESPONSES_ID,
                type="function_call",
                call_id=call_id,
                name=name,
                arguments=arguments,
                provider_data={"response_id": "chatcmpl-one"},
            )
            adapter.handle(
                self._event(
                    "response.output_item.added",
                    output_index=output_index,
                    item=item,
                )
            )
            adapter.handle(
                self._event(
                    "response.function_call_arguments.delta",
                    output_index=output_index,
                    item_id=FAKE_RESPONSES_ID,
                    delta=arguments,
                )
            )
            adapter.handle(
                self._event(
                    "response.output_item.done",
                    output_index=output_index,
                    item=item,
                )
            )
        adapter.handle(
            self._event(
                "response.completed",
                response=SimpleNamespace(
                    id=FAKE_RESPONSES_ID,
                    output=[],
                    usage=None,
                ),
            )
        )
        adapter.record_converted_message_count(7)
        adapter.handle(
            self._event(
                "response.created",
                response=SimpleNamespace(id=FAKE_RESPONSES_ID),
            )
        )
        adapter.handle(
            self._event(
                "response.completed",
                response=SimpleNamespace(
                    id=FAKE_RESPONSES_ID,
                    output=[
                        SimpleNamespace(
                            provider_data={"response_id": "chatcmpl-two"}
                        )
                    ],
                    usage=None,
                ),
            )
        )
        adapter.finish()

        with self.Session() as db:
            steps = list(
                db.scalars(
                    select(NativeAgentStep)
                    .where(NativeAgentStep.run_id == self.run_id)
                    .order_by(NativeAgentStep.sequence)
                ).all()
            )
            self.assertEqual(2, len(steps))
            self.assertEqual(2, len({step.model_call_id for step in steps}))
            self.assertEqual(
                ["chatcmpl-one", "chatcmpl-two"],
                [step.provider_response_id for step in steps],
            )
            self.assertNotIn(
                FAKE_RESPONSES_ID,
                [step.model_call_id for step in steps]
                + [step.provider_response_id for step in steps],
            )
            self.assertEqual([4, 7], [step.converted_message_count for step in steps])
            self.assertEqual([2, 2], [step.execution_attempt for step in steps])
            self.assertEqual([1, 2], [step.model_call_ordinal for step in steps])
            self.assertEqual(
                ["siliconflow", "siliconflow"],
                [step.model_provider for step in steps],
            )
            self.assertEqual(
                ["chat_completions", "chat_completions"],
                [step.model_api_shape for step in steps],
            )
            self.assertTrue(all(step.latency_ms is not None for step in steps))
            events = list(
                db.scalars(
                    select(NativeAgentEvent)
                    .where(
                        NativeAgentEvent.run_id == self.run_id,
                        NativeAgentEvent.event_type
                        == "response.function_call.arguments.done",
                    )
                    .order_by(NativeAgentEvent.sequence)
                ).all()
            )
            payloads = [json.loads(event.payload_json) for event in events]
            self.assertEqual(["call-a", "call-b"], [item["tool_call_id"] for item in payloads])
            self.assertEqual(2, len({item["item_id"] for item in payloads}))

    def test_final_arguments_mismatch_fails_closed(self) -> None:
        adapter = NativeModelEventAdapter(
            run_id=self.run_id,
            execution_attempt=1,
            route=self.route,
            store=self.store,
        )
        adapter.record_converted_message_count(2)
        adapter.handle(
            self._event(
                "response.created",
                response=SimpleNamespace(id=FAKE_RESPONSES_ID),
            )
        )
        item = SimpleNamespace(
            id=FAKE_RESPONSES_ID,
            type="function_call",
            call_id="call-mismatch",
            name="generate_image",
            arguments='{"prompt":"final"}',
            provider_data={"response_id": "chatcmpl-mismatch"},
        )
        adapter.handle(
            self._event(
                "response.output_item.added",
                output_index=0,
                item=item,
            )
        )
        adapter.handle(
            self._event(
                "response.function_call_arguments.delta",
                output_index=0,
                delta='{"prompt":"other"}',
            )
        )
        with self.assertRaisesRegex(
            NativeModelEventAdapterError,
            "累计参数与完成参数不一致",
        ):
            adapter.handle(
                self._event(
                    "response.output_item.done",
                    output_index=0,
                    item=item,
                )
            )

    def test_ambiguous_or_incomplete_function_events_fail_closed(self) -> None:
        def started(attempt: int) -> NativeModelEventAdapter:
            adapter = NativeModelEventAdapter(
                run_id=self.run_id,
                execution_attempt=attempt,
                route=self.route,
                store=self.store,
            )
            adapter.record_converted_message_count(2)
            adapter.handle(
                self._event(
                    "response.created",
                    response=SimpleNamespace(id=FAKE_RESPONSES_ID),
                )
            )
            return adapter

        missing_call_id = started(10)
        with self.assertRaisesRegex(NativeModelEventAdapterError, "缺少真实 call ID"):
            missing_call_id.handle(
                self._event(
                    "response.output_item.added",
                    output_index=0,
                    item=SimpleNamespace(
                        id=FAKE_RESPONSES_ID,
                        type="function_call",
                        call_id="",
                        name="generate_image",
                        provider_data=None,
                    ),
                )
            )

        duplicate = started(11)
        item = SimpleNamespace(
            id=FAKE_RESPONSES_ID,
            type="function_call",
            call_id="call-one",
            name="generate_image",
            provider_data=None,
        )
        duplicate.handle(
            self._event(
                "response.output_item.added",
                output_index=0,
                item=item,
            )
        )
        with self.assertRaisesRegex(NativeModelEventAdapterError, "重复"):
            duplicate.handle(
                self._event(
                    "response.output_item.added",
                    output_index=0,
                    item=item,
                )
            )

        conflicting_provider = started(12)
        conflicting_provider.handle(
            self._event(
                "response.output_item.added",
                output_index=0,
                item=SimpleNamespace(
                    id="text-one",
                    type="message",
                    provider_data={"response_id": "chatcmpl-a"},
                ),
            )
        )
        with self.assertRaisesRegex(NativeModelEventAdapterError, "互相冲突"):
            conflicting_provider.handle(
                self._event(
                    "response.output_item.added",
                    output_index=1,
                    item=SimpleNamespace(
                        id="text-two",
                        type="message",
                        provider_data={"response_id": "chatcmpl-b"},
                    ),
                )
            )

        incomplete = started(13)
        incomplete.handle(
            self._event(
                "response.output_item.added",
                output_index=0,
                item=SimpleNamespace(
                    id=FAKE_RESPONSES_ID,
                    type="function_call",
                    call_id="call-incomplete",
                    name="generate_image",
                    provider_data=None,
                ),
            )
        )
        with self.assertRaisesRegex(NativeModelEventAdapterError, "参数未完成"):
            incomplete.handle(
                self._event(
                    "response.completed",
                    response=SimpleNamespace(
                        id=FAKE_RESPONSES_ID,
                        output=[],
                        usage=None,
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
