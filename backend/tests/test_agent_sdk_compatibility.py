import unittest

from scripts.check_agent_sdk_compatibility import (
    ProviderConfig,
    build_openai_provider,
    load_provider_configs,
    redact_text,
    summarize_usage,
)


class FakeUsage:
    input_tokens = 11
    output_tokens = 7
    total_tokens = 18


class FakeResponse:
    usage = FakeUsage()


class AgentSDKCompatibilityTests(unittest.TestCase):
    def test_config_uses_explicit_probe_model_for_both_providers(self):
        configs = load_provider_configs("gpt-5.5")

        self.assertEqual(configs["huomiao"].model, "gpt-5.5")
        self.assertEqual(configs["lio"].model, "gpt-5.5")

    def test_provider_forces_responses_and_disables_client_retries(self):
        provider = build_openai_provider(
            ProviderConfig(
                name="test",
                base_url="https://gateway.example/v1",
                api_key="private-key",
                model="gpt-5.5",
            ),
            timeout_seconds=12,
        )

        self.assertTrue(provider._use_responses)
        self.assertEqual(provider._client.max_retries, 0)

    def test_redaction_removes_keys_and_authorization_tokens(self):
        raw = "secret-123 Authorization: Bearer token-456"

        redacted = redact_text(raw, ["secret-123"])

        self.assertNotIn("secret-123", redacted)
        self.assertNotIn("token-456", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_usage_summary_is_bounded_to_numeric_metadata(self):
        summary = summarize_usage([FakeResponse(), FakeResponse()])

        self.assertEqual(
            summary,
            {
                "requests": 2,
                "input_tokens": 22,
                "output_tokens": 14,
                "total_tokens": 36,
            },
        )


if __name__ == "__main__":
    unittest.main()
