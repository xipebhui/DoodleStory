import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.llm import call_lio_json


class TextFallbackTest(unittest.TestCase):
    @patch("app.services.llm.time.sleep")
    @patch("app.services.llm.create_text_fallback_client")
    @patch("app.services.llm.create_lio_client")
    @patch("app.services.llm.get_settings")
    @patch("app.services.llm.call_openai_compatible_json_once")
    def test_lio_failure_retries_only_with_text_fallback_model(
        self,
        call_once,
        get_settings,
        create_lio_client,
        create_text_fallback_client,
        sleep,
    ) -> None:
        get_settings.return_value = SimpleNamespace(
            lio_model="gemini-3.1-flash-lite-preview-thinking-minimal",
            lio_temperature=0.2,
            text_fallback_model="gpt-5.4",
            text_fallback_max_attempts=2,
            text_fallback_retry_backoff_seconds=0,
        )
        create_lio_client.return_value = object()
        create_text_fallback_client.return_value = object()
        call_once.side_effect = [
            RuntimeError("gemini busy"),
            RuntimeError("fallback busy"),
            {"ok": True},
        ]

        result = call_lio_json(
            system_prompt="system",
            user_prompt="user",
            prompt_name="unit_test.md",
        )

        self.assertEqual({"ok": True}, result)
        self.assertEqual(["lio", "text_fallback", "text_fallback"], [call.kwargs["provider"] for call in call_once.call_args_list])
        self.assertEqual(
            [
                "gemini-3.1-flash-lite-preview-thinking-minimal",
                "gpt-5.4",
                "gpt-5.4",
            ],
            [call.kwargs["model"] for call in call_once.call_args_list],
        )
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
