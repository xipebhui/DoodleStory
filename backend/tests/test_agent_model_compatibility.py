import json
import unittest

import requests

from scripts.check_agent_model_compatibility import (
    ProviderConfig,
    ProviderProbe,
    extract_chat_text,
    extract_responses_text,
    is_retryable_failure,
    parse_capabilities,
    redact_text,
)


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


class AgentModelCompatibilityTests(unittest.TestCase):
    def test_retryable_failure_matrix(self):
        for status_code in (408, 409, 429, 500, 502, 503, 504):
            with self.subTest(status_code=status_code):
                self.assertTrue(is_retryable_failure(status_code=status_code))

        for status_code in (400, 401, 403, 404, 422):
            with self.subTest(status_code=status_code):
                self.assertFalse(is_retryable_failure(status_code=status_code))

        self.assertTrue(is_retryable_failure(exception=requests.Timeout("late")))
        self.assertTrue(
            is_retryable_failure(exception=requests.ConnectionError("offline"))
        )
        self.assertFalse(is_retryable_failure(exception=ValueError("invalid schema")))
        self.assertFalse(
            is_retryable_failure(
                status_code=503,
                response_text='{"error":{"code":"invalid_request",'
                '"message":"不支持此 API 路径"}}',
            )
        )

    def test_redact_text_removes_configured_key_and_bearer_token(self):
        raw = "key=secret-123 Authorization: Bearer token-456"

        redacted = redact_text(raw, ["secret-123"])

        self.assertNotIn("secret-123", redacted)
        self.assertNotIn("token-456", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_extract_chat_text_supports_string_and_content_parts(self):
        self.assertEqual(
            extract_chat_text({"choices": [{"message": {"content": " hello "}}]}),
            "hello",
        )
        self.assertEqual(
            extract_chat_text(
                {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "text", "text": "hello "},
                                    {"type": "text", "text": "world"},
                                ]
                            }
                        }
                    ]
                }
            ),
            "hello world",
        )

    def test_extract_responses_text_supports_both_shapes(self):
        self.assertEqual(extract_responses_text({"output_text": "ok"}), "ok")
        self.assertEqual(
            extract_responses_text(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "response "},
                                {"type": "output_text", "text": "ok"},
                            ],
                        }
                    ]
                }
            ),
            "response ok",
        )

    def test_parse_capabilities_rejects_unknown_value(self):
        self.assertEqual(parse_capabilities("chat,tools"), ["chat", "tools"])
        with self.assertRaises(Exception):
            parse_capabilities("chat,unknown")

    def test_chat_probe_sends_no_retry_metadata_and_accepts_marker(self):
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {"choices": [{"message": {"content": "CHAT_OK"}}]},
                    text=json.dumps({"ok": True}),
                )
            ]
        )
        probe = ProviderProbe(
            ProviderConfig(
                name="test",
                base_url="https://gateway.example/v1",
                api_key="private-key",
                model="test-model",
            ),
            timeout_seconds=12,
            session=session,
        )

        result = probe.run_capability("chat")

        self.assertEqual(result["status"], "pass")
        self.assertEqual(session.requests[0][0], "https://gateway.example/v1/chat/completions")
        self.assertEqual(session.requests[0][1]["timeout"], 12)
        self.assertNotIn("retry", session.requests[0][1])

    def test_http_error_is_redacted_and_classified(self):
        session = FakeSession(
            [FakeResponse(503, text="Authorization: Bearer private-key unavailable")]
        )
        probe = ProviderProbe(
            ProviderConfig(
                name="test",
                base_url="https://gateway.example/v1",
                api_key="private-key",
                model="test-model",
            ),
            timeout_seconds=12,
            session=session,
        )

        result = probe.run_capability("chat")

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["http_status"], 503)
        self.assertTrue(result["retryable"])
        self.assertNotIn("private-key", result["error"])


if __name__ == "__main__":
    unittest.main()
