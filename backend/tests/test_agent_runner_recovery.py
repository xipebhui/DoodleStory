import asyncio
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import AgentConversation, AgentMessage, AgentRun, AgentStep, User, new_id
from app.models.enums import AgentMessageRole, AgentRunStatus, AgentStepStatus, AgentStepType
from app.services import agent_runner
from app.services.agent_model_router import (
    AgentModelResult,
    AgentModelRoute,
    AgentModelRouter,
    AgentProviderConfig,
)


class FakeSuccessfulRouter:
    def __init__(self, answer: str = "真实模型回答"):
        self.answer = answer
        self.call_count = 0

    async def run(self, input_items, observer):
        self.call_count += 1
        route = AgentModelRoute(
            provider="huomiao",
            model="gpt-5.5",
            api_shape="responses",
            attempt=1,
        )
        await observer.attempt_started(route)
        result = AgentModelResult(
            final_output=self.answer,
            usage={"requests": 1, "input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            provider_request_id="provider-request-id",
            raw_result=None,
            route=route,
        )
        await observer.attempt_succeeded(route, result, 25)
        return result


class ExplodingRouter:
    def __init__(self):
        self.call_count = 0

    async def run(self, input_items, observer):
        self.call_count += 1
        raise AssertionError("model must not be called")


class InjectedHTTPError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def fault_injection_router(outcomes):
    router = AgentModelRouter.__new__(AgentModelRouter)
    router.settings = SimpleNamespace(agent_primary_retry_attempts=1, agent_retry_backoff_seconds=0)
    router.model = "gpt-5.5"
    router.primary = AgentProviderConfig("huomiao", "https://primary.example/v1", "primary-key")
    router.fallback = AgentProviderConfig("lio", "https://fallback.example/v1", "fallback-key")

    async def invoke(config, route, input_items):
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return AgentModelResult(
            final_output=outcome,
            usage={"requests": 1, "input_tokens": 8, "output_tokens": 4, "total_tokens": 12},
            provider_request_id=f"{route.provider}-request-id",
            raw_result=None,
            route=route,
        )

    router._invoke = invoke
    return router


class AgentRunnerRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        agent_runner._active_run_ids.clear()
        agent_runner._active_run_ids_lock = None
        agent_runner._agent_queue = None
        self.settings = SimpleNamespace(agent_context_message_limit=200)

    def create_run(self, *, status: AgentRunStatus = AgentRunStatus.queued):
        with self.Session() as db:
            user = User(email=f"runner-{new_id()}@example.com", password_hash="hash")
            conversation = AgentConversation(owner=user, title="恢复测试")
            turn_id = new_id()
            message = AgentMessage(
                conversation=conversation,
                turn_id=turn_id,
                role=AgentMessageRole.user,
                content="请记住第一轮内容",
                sequence=1,
            )
            run = AgentRun(conversation=conversation, turn_id=turn_id, status=status)
            db.add_all([user, conversation, message, run])
            db.commit()
            return run.id, conversation.id, turn_id

    def process(self, run_id: str, router) -> None:
        with (
            patch("app.services.agent_runner.database.SessionLocal", self.Session),
            patch("app.services.agent_runner.get_settings", return_value=self.settings),
        ):
            asyncio.run(agent_runner.process_agent_run(run_id, router=router))

    def test_success_checkpoints_model_and_single_final_message(self):
        run_id, conversation_id, turn_id = self.create_run()
        router = FakeSuccessfulRouter()

        self.process(run_id, router)
        self.process(run_id, router)

        with self.Session() as db:
            run = db.get(AgentRun, run_id)
            assistant_messages = db.scalars(
                select(AgentMessage).where(
                    AgentMessage.conversation_id == conversation_id,
                    AgentMessage.turn_id == turn_id,
                    AgentMessage.role == AgentMessageRole.assistant,
                )
            ).all()
            steps = db.scalars(select(AgentStep).where(AgentStep.run_id == run_id)).all()
        self.assertEqual(AgentRunStatus.succeeded, run.status)
        self.assertEqual(1, router.call_count)
        self.assertEqual(["真实模型回答"], [message.content for message in assistant_messages])
        self.assertEqual(1, sum(step.step_type == AgentStepType.final for step in steps))
        self.assertEqual(1, sum(step.step_type == AgentStepType.model_call for step in steps))

    def test_successful_model_checkpoint_finalizes_without_model_replay(self):
        run_id, conversation_id, turn_id = self.create_run(status=AgentRunStatus.running)
        with self.Session() as db:
            db.add(
                AgentStep(
                    run_id=run_id,
                    sequence=1,
                    step_type=AgentStepType.model_call,
                    status=AgentStepStatus.succeeded,
                    provider="huomiao",
                    model="gpt-5.5",
                    api_shape="responses",
                    attempt=1,
                    output_ref=json.dumps({"assistant_content": "checkpoint 回答"}, ensure_ascii=False),
                )
            )
            db.commit()
        router = ExplodingRouter()

        self.process(run_id, router)

        with self.Session() as db:
            run = db.get(AgentRun, run_id)
            answer_count = db.scalar(
                select(func.count(AgentMessage.id)).where(
                    AgentMessage.conversation_id == conversation_id,
                    AgentMessage.turn_id == turn_id,
                    AgentMessage.role == AgentMessageRole.assistant,
                )
            )
        self.assertEqual(AgentRunStatus.succeeded, run.status)
        self.assertEqual(0, router.call_count)
        self.assertEqual(1, answer_count)

    def test_interrupted_running_step_is_failed_before_safe_replay(self):
        run_id, _, _ = self.create_run(status=AgentRunStatus.running)
        with self.Session() as db:
            run = db.get(AgentRun, run_id)
            run.model_call_count = 1
            db.add(
                AgentStep(
                    run_id=run_id,
                    sequence=1,
                    step_type=AgentStepType.model_call,
                    status=AgentStepStatus.running,
                    provider="huomiao",
                    model="gpt-5.5",
                    api_shape="responses",
                    attempt=1,
                )
            )
            db.commit()

        self.process(run_id, FakeSuccessfulRouter("恢复后的回答"))

        with self.Session() as db:
            run = db.get(AgentRun, run_id)
            steps = db.scalars(
                select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.sequence)
            ).all()
        self.assertEqual(AgentRunStatus.succeeded, run.status)
        self.assertEqual(2, run.model_call_count)
        self.assertEqual("AgentWorkerInterrupted", steps[0].error_code)
        self.assertEqual(AgentStepStatus.failed, steps[0].status)
        self.assertEqual(AgentStepStatus.succeeded, steps[1].status)

    def test_recovery_enqueues_only_recoverable_runs(self):
        queued_id, _, _ = self.create_run(status=AgentRunStatus.queued)
        succeeded_id, _, _ = self.create_run(status=AgentRunStatus.succeeded)
        queue = asyncio.Queue()

        async def recover():
            with patch("app.services.agent_runner.database.SessionLocal", self.Session):
                agent_runner._agent_queue = queue
                return await agent_runner.recover_agent_runs()

        recovered_count = asyncio.run(recover())
        agent_runner._agent_queue = None

        self.assertEqual(1, recovered_count)
        self.assertEqual(queued_id, queue.get_nowait())
        self.assertNotEqual(succeeded_id, queued_id)

    def test_temporary_failures_checkpoint_retry_and_fallback_with_one_final_answer(self):
        run_id, conversation_id, turn_id = self.create_run()
        router = fault_injection_router(
            [
                InjectedHTTPError(503, "upstream temporarily unavailable"),
                InjectedHTTPError(503, "upstream temporarily unavailable"),
                "备用线路回答",
            ]
        )

        self.process(run_id, router)

        with self.Session() as db:
            run = db.get(AgentRun, run_id)
            steps = db.scalars(
                select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.sequence)
            ).all()
            answers = db.scalars(
                select(AgentMessage).where(
                    AgentMessage.conversation_id == conversation_id,
                    AgentMessage.turn_id == turn_id,
                    AgentMessage.role == AgentMessageRole.assistant,
                )
            ).all()
        model_steps = [step for step in steps if step.step_type == AgentStepType.model_call]
        self.assertEqual(AgentRunStatus.succeeded, run.status)
        self.assertEqual(["huomiao", "huomiao", "lio"], [step.provider for step in model_steps])
        self.assertEqual(
            [AgentStepStatus.failed, AgentStepStatus.failed, AgentStepStatus.succeeded],
            [step.status for step in model_steps],
        )
        self.assertEqual("huomiao", model_steps[-1].fallback_from)
        self.assertEqual(1, len(answers))
        self.assertEqual("备用线路回答", answers[0].content)
        self.assertEqual(1, sum(step.step_type == AgentStepType.final for step in steps))

    def test_permanent_provider_error_stops_without_fallback_or_answer(self):
        run_id, conversation_id, turn_id = self.create_run()
        router = fault_injection_router([InjectedHTTPError(503, "no available channel for model")])

        self.process(run_id, router)

        with self.Session() as db:
            run = db.get(AgentRun, run_id)
            model_steps = db.scalars(
                select(AgentStep).where(
                    AgentStep.run_id == run_id,
                    AgentStep.step_type == AgentStepType.model_call,
                )
            ).all()
            answer_count = db.scalar(
                select(func.count(AgentMessage.id)).where(
                    AgentMessage.conversation_id == conversation_id,
                    AgentMessage.turn_id == turn_id,
                    AgentMessage.role == AgentMessageRole.assistant,
                )
            )
        self.assertEqual(AgentRunStatus.failed, run.status)
        self.assertEqual("AgentModelPermanentError", run.error_code)
        self.assertEqual(1, len(model_steps))
        self.assertEqual("huomiao", model_steps[0].provider)
        self.assertEqual(0, answer_count)


if __name__ == "__main__":
    unittest.main()
