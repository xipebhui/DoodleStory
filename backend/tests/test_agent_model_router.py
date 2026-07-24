import asyncio
from types import SimpleNamespace
import unittest

from app.services.agent_model_router import (
    AgentModelFailure,
    AgentModelResult,
    AgentModelRoute,
    AgentModelRouter,
    AgentModelRoutingError,
    AgentProviderConfig,
    classify_agent_model_error,
    extract_agent_provider_request_id,
    redact_agent_error,
)


class FakeHTTPError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class NullObserver:
    async def attempt_started(self, route):
        return None

    async def attempt_succeeded(self, route, result, latency_ms):
        return None

    async def attempt_failed(self, route, failure, latency_ms):
        return None


def temporary_failure() -> AgentModelFailure:
    return AgentModelFailure(
        code="AgentModelTemporaryError",
        safe_message="temporary",
        retryable=True,
        status_code=503,
        internal_error_ref="Fake:503",
    )


def permanent_failure() -> AgentModelFailure:
    return AgentModelFailure(
        code="AgentModelPermanentError",
        safe_message="permanent",
        retryable=False,
        status_code=503,
        internal_error_ref="Fake:503",
    )


def make_router(outcomes):
    router = AgentModelRouter.__new__(AgentModelRouter)
    router.settings = SimpleNamespace(agent_primary_retry_attempts=1, agent_retry_backoff_seconds=0)
    router.model = "gpt-5.5"
    router.primary = AgentProviderConfig("huomiao", "https://primary.example/v1", "primary-key")
    router.fallback = AgentProviderConfig("lio", "https://fallback.example/v1", "fallback-key")
    routes = []

    async def run_attempt(config, route, input_items, observer):
        routes.append(route)
        outcome = outcomes.pop(0)
        if isinstance(outcome, AgentModelFailure):
            return None, outcome
        return AgentModelResult(
            final_output=outcome,
            usage={"requests": 1, "input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            provider_request_id="request-id",
            raw_result=None,
            route=route,
        ), None

    router._run_attempt = run_attempt
    return router, routes


class AgentModelRouterTests(unittest.TestCase):
    def test_provider_request_id_uses_response_id_when_request_id_is_absent(self):
        response = SimpleNamespace(request_id=None, response_id="response-id")

        self.assertEqual("response-id", extract_agent_provider_request_id([response]))

    def test_runtime_error_redaction_removes_configured_and_authorization_secrets(self):
        redacted = redact_agent_error(
            "private-key Authorization: Bearer authorization-token",
            ["private-key"],
        )

        self.assertNotIn("private-key", redacted)
        self.assertNotIn("authorization-token", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_semantic_temporary_503_is_retryable(self):
        failure = classify_agent_model_error(FakeHTTPError(503, "upstream temporarily unavailable"))

        self.assertTrue(failure.retryable)
        self.assertEqual("AgentModelTemporaryError", failure.code)

    def test_no_channel_503_is_permanent(self):
        failure = classify_agent_model_error(FakeHTTPError(503, "no available channel for model"))

        self.assertFalse(failure.retryable)
        self.assertEqual("AgentModelPermanentError", failure.code)

    def test_stream_interruption_408_is_temporary_even_when_provider_labels_invalid_request(self):
        failure = classify_agent_model_error(
            FakeHTTPError(
                408,
                "invalid_request_error: stream disconnected before completion: stream closed before response.completed",
            )
        )

        self.assertTrue(failure.retryable)
        self.assertEqual("AgentModelTemporaryError", failure.code)

    def test_primary_temporary_errors_retry_then_fallback_once(self):
        router, routes = make_router([temporary_failure(), temporary_failure(), "fallback answer"])

        result = asyncio.run(router.run([{"role": "user", "content": "hello"}], NullObserver()))

        self.assertEqual("fallback answer", result.final_output)
        self.assertEqual(["huomiao", "huomiao", "lio"], [route.provider for route in routes])
        self.assertEqual([1, 2, 1], [route.attempt for route in routes])
        self.assertEqual("huomiao", routes[-1].fallback_from)
        self.assertEqual("AgentModelTemporaryError", routes[-1].fallback_reason)

    def test_permanent_error_does_not_retry_or_fallback(self):
        router, routes = make_router([permanent_failure()])

        with self.assertRaises(AgentModelRoutingError):
            asyncio.run(router.run([{"role": "user", "content": "hello"}], NullObserver()))

        self.assertEqual(["huomiao"], [route.provider for route in routes])


if __name__ == "__main__":
    unittest.main()
