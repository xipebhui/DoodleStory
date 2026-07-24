import asyncio
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mlflow
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import AgentConversation, AgentMessage, AgentRun, AgentStep, User, new_id
from app.models.enums import AgentMessageRole, AgentRunStatus, AgentStepType
from app.services import agent_observability, agent_runner
from app.services.agent_model_router import (
    AgentModelResult,
    AgentModelRouter,
    AgentProviderConfig,
)


class InjectedHTTPError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def make_settings(tracking_uri: str, *, enabled: bool = True):
    return SimpleNamespace(
        mlflow_tracing_enabled=enabled,
        mlflow_tracking_uri=tracking_uri,
        mlflow_experiment_name="agent-observability-tests",
        mlflow_trace_content=False,
        text_fallback_api_key="primary-secret",
        lio_api_key="fallback-secret",
        image_gateway_api_key="image-secret",
        agent_context_message_limit=200,
        agent_model="gpt-5.5",
        app_env="test",
    )


def fault_injection_router(outcomes):
    router = AgentModelRouter.__new__(AgentModelRouter)
    router.settings = SimpleNamespace(agent_primary_retry_attempts=1, agent_retry_backoff_seconds=0)
    router.model = "gpt-5.5"
    router.primary = AgentProviderConfig("huomiao", "https://primary.example/v1", "primary-secret")
    router.fallback = AgentProviderConfig("lio", "https://fallback.example/v1", "fallback-secret")

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


class AgentObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        agent_observability.reset_agent_observability_for_tests()
        agent_runner._active_run_ids.clear()
        agent_runner._active_run_ids_lock = None
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.temp_dir = TemporaryDirectory()
        self.tracking_uri = f"sqlite:///{Path(self.temp_dir.name) / 'mlflow.db'}"
        self.settings = make_settings(self.tracking_uri)

    def tearDown(self) -> None:
        mlflow.flush_trace_async_logging(terminate=True)
        agent_observability.reset_agent_observability_for_tests()
        self.temp_dir.cleanup()

    def create_run(self) -> str:
        with self.Session() as db:
            user = User(email=f"trace-{new_id()}@example.com", password_hash="hash")
            conversation = AgentConversation(owner=user, title="trace test")
            turn_id = new_id()
            message = AgentMessage(
                conversation=conversation,
                turn_id=turn_id,
                role=AgentMessageRole.user,
                content="private user content",
                sequence=1,
            )
            run = AgentRun(conversation=conversation, turn_id=turn_id)
            db.add_all([user, conversation, message, run])
            db.commit()
            return run.id

    def process(self, run_id: str, router) -> None:
        with (
            patch("app.services.agent_runner.database.SessionLocal", self.Session),
            patch("app.services.agent_runner.get_settings", return_value=self.settings),
        ):
            asyncio.run(agent_runner.process_agent_run(run_id, router=router))
        mlflow.flush_trace_async_logging()

    def traces_for(self, run_id: str):
        experiment = mlflow.get_experiment_by_name(self.settings.mlflow_experiment_name)
        return mlflow.search_traces(
            locations=[experiment.experiment_id],
            filter_string=f"tags.agent_run_id = '{run_id}'",
            return_type="list",
            include_spans=True,
            flush=True,
        )

    def test_disabled_does_not_import_or_initialize_mlflow(self):
        settings = make_settings("", enabled=False)

        with patch.object(agent_observability, "_mlflow") as load_mlflow:
            agent_observability.initialize_agent_observability(settings)

        load_mlflow.assert_not_called()
        self.assertFalse(agent_observability.is_agent_observability_enabled())

    def test_enabled_missing_tracking_uri_fails_explicitly(self):
        settings = make_settings("")

        with self.assertRaises(agent_observability.AgentObservabilityConfigurationError):
            agent_observability.initialize_agent_observability(settings)

    def test_enabled_unreachable_tracking_backend_fails_initialization(self):
        class BrokenMlflow:
            @staticmethod
            def set_tracking_uri(uri):
                return None

            @staticmethod
            def set_experiment(name):
                raise ConnectionError("tracking backend unreachable")

        with (
            patch.object(agent_observability, "_mlflow", return_value=BrokenMlflow()),
            self.assertRaises(agent_observability.AgentObservabilityConfigurationError),
        ):
            agent_observability.initialize_agent_observability(self.settings)

    def test_redactor_removes_secrets_urls_paths_and_default_content(self):
        agent_observability._configured_secrets = ("secret-value",)

        redacted = agent_observability.sanitize_trace_value(
            {
                "authorization": "Bearer abc",
                "resource": "https://example.com/private/image.png",
                "file": "/Users/example/private/file.png",
                "safe": "contains secret-value",
                "prompt": "private prompt",
            },
            allow_content=False,
        )

        serialized = json.dumps(redacted)
        self.assertNotIn("abc", serialized)
        self.assertNotIn("example.com", serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("secret-value", serialized)
        self.assertNotIn("private prompt", serialized)

    def test_fallback_attempts_share_one_root_trace_and_match_database_steps(self):
        agent_observability.initialize_agent_observability(self.settings)
        run_id = self.create_run()
        router = fault_injection_router(
            [
                InjectedHTTPError(503, "upstream temporarily unavailable"),
                InjectedHTTPError(503, "upstream temporarily unavailable"),
                "fallback success",
            ]
        )

        self.process(run_id, router)

        traces = self.traces_for(run_id)
        self.assertEqual(1, len(traces))
        spans = traces[0].data.spans
        root_spans = [span for span in spans if span.name == "agent.run"]
        model_spans = [span for span in spans if span.name == "agent.model_call"]
        self.assertEqual(1, len(root_spans))
        self.assertEqual(3, len(model_spans))
        self.assertEqual(["huomiao", "huomiao", "lio"], [
            span.attributes["provider"] for span in model_spans
        ])
        self.assertEqual("huomiao", model_spans[-1].attributes["fallback_from"])
        self.assertEqual(8, model_spans[-1].attributes["input_tokens"])
        self.assertEqual("succeeded", root_spans[0].attributes["run_status"])
        self.assertNotIn("private user content", json.dumps(traces[0].to_dict()))

        with self.Session() as db:
            run = db.get(AgentRun, run_id)
            model_steps = db.scalars(
                select(AgentStep)
                .where(
                    AgentStep.run_id == run_id,
                    AgentStep.step_type == AgentStepType.model_call,
                )
                .order_by(AgentStep.sequence)
            ).all()
        self.assertEqual(AgentRunStatus.succeeded, run.status)
        self.assertEqual(
            [step.id for step in model_steps],
            [span.attributes["agent_step_id"] for span in model_spans],
        )

    def test_permanent_error_has_no_fallback_success_span(self):
        agent_observability.initialize_agent_observability(self.settings)
        run_id = self.create_run()
        router = fault_injection_router(
            [InjectedHTTPError(503, "no available channel for model")]
        )

        self.process(run_id, router)

        trace = self.traces_for(run_id)[0]
        spans = trace.data.spans
        model_spans = [span for span in spans if span.name == "agent.model_call"]
        self.assertEqual(["huomiao"], [span.attributes["provider"] for span in model_spans])
        self.assertEqual("failed", [
            span for span in spans if span.name == "agent.run"
        ][0].attributes["run_status"])
        self.assertEqual("ERROR", trace.info.state.value)

    def test_reporting_failure_is_logged_without_changing_business_success(self):
        agent_observability.initialize_agent_observability(self.settings)
        run_id = self.create_run()
        router = fault_injection_router(["business success"])

        with (
            patch.object(mlflow, "start_span", side_effect=RuntimeError("trace backend down")),
            self.assertLogs("app.services.agent_observability", level=logging.ERROR) as logs,
        ):
            self.process(run_id, router)

        with self.Session() as db:
            run = db.get(AgentRun, run_id)
        self.assertEqual(AgentRunStatus.succeeded, run.status)
        self.assertTrue(any("observability_error" in message for message in logs.output))


if __name__ == "__main__":
    unittest.main()
