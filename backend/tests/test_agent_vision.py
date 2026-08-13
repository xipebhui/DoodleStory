import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from app.services.agent_vision import AgentVisionError, inspect_image_asset


class AgentVisionTests(unittest.TestCase):
    def test_inspection_uses_siliconflow_vision_without_retry(self) -> None:
        checks = ["historical_mechanism_alignment", "modern_object_exclusion"]
        response = json.dumps(
            {
                "verdict": "accept",
                "scores": {
                    "historical_mechanism_alignment": 0.95,
                    "modern_object_exclusion": 1.0,
                },
                "issues": [],
            }
        )
        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "candidate.png"
            image_path.write_bytes(b"not-empty-test-image")
            asset = SimpleNamespace(content_type="image/png")
            with (
                patch(
                    "app.services.agent_vision.get_settings",
                    return_value=SimpleNamespace(
                        siliconflow_vision_model="Qwen/Qwen3-VL-32B-Instruct"
                    ),
                ),
                patch(
                    "app.services.agent_vision.materialize_asset_to_local",
                    return_value=image_path,
                ),
                patch(
                    "app.services.agent_vision._chat_multimodal",
                    return_value=response,
                ) as chat,
            ):
                result, provider, model, latency_ms = inspect_image_asset(
                    asset,
                    checks=checks,
                    expected={"story_beat": "test"},
                )

        self.assertEqual("accept", result.verdict)
        self.assertEqual("siliconflow", provider)
        self.assertEqual("Qwen/Qwen3-VL-32B-Instruct", model)
        self.assertGreaterEqual(latency_ms, 0)
        call = chat.call_args.kwargs
        self.assertEqual(0, call["max_retries"])
        self.assertEqual("agent_inspect_image", call["prompt_name"])
        self.assertTrue(call["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_missing_siliconflow_vision_model_fails_closed(self) -> None:
        with patch(
            "app.services.agent_vision.get_settings",
            return_value=SimpleNamespace(siliconflow_vision_model=""),
        ):
            with self.assertRaisesRegex(
                AgentVisionError,
                "SILICONFLOW_VISION_MODEL 未配置",
            ):
                inspect_image_asset(
                    SimpleNamespace(content_type="image/png"),
                    checks=["composition"],
                    expected={},
                )

    def test_unknown_score_key_fails_closed(self) -> None:
        response = json.dumps(
            {
                "verdict": "accept",
                "scores": {"composition": 1.0, "unexpected": 1.0},
                "issues": [],
            }
        )
        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "candidate.png"
            image_path.write_bytes(b"not-empty-test-image")
            with (
                patch(
                    "app.services.agent_vision.get_settings",
                    return_value=SimpleNamespace(
                        siliconflow_vision_model="Qwen/Qwen3-VL-32B-Instruct"
                    ),
                ),
                patch(
                    "app.services.agent_vision.materialize_asset_to_local",
                    return_value=image_path,
                ),
                patch(
                    "app.services.agent_vision._chat_multimodal",
                    return_value=response,
                ),
            ):
                with self.assertRaisesRegex(
                    AgentVisionError,
                    "评分项与请求 checks 不一致",
                ):
                    inspect_image_asset(
                        SimpleNamespace(content_type="image/png"),
                        checks=["composition"],
                        expected={},
                    )


if __name__ == "__main__":
    unittest.main()
