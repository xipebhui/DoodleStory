import json
import unittest
from unittest.mock import patch

from app.models.enums import ImageCountMode, PanelType
from app.services.llm import LLMConfigError, LLMResponseError, segment_story


class StorySegmentationTest(unittest.TestCase):
    def test_original_story_segmentation_uses_llm_and_preserves_text(self) -> None:
        original_text = "我三叔特别的喜欢我是有原因的\n他有时候工地夜班干完活回来"
        with patch(
            "app.services.llm.call_siliconflow_json",
            return_value={
                "panels": [
                    {"panel_order": 1, "text": "我三叔特别的喜欢我是有原因的\n"},
                    {"panel_order": 2, "text": "他有时候工地夜班干完活回来"},
                ]
            },
        ) as call_json:
            result = segment_story(
                original_text=original_text,
                image_count_mode=ImageCountMode.auto,
                requested_image_count=None,
            )

        self.assertEqual("segment_story_v1.md", call_json.call_args.kwargs["prompt_name"])
        self.assertEqual(0.2, call_json.call_args.kwargs["temperature"])
        user_payload = json.loads(call_json.call_args.kwargs["user_prompt"])
        self.assertEqual(50, user_payload["max_panel_text_chars"])
        self.assertIn("自动判断", user_payload["count_instruction"])
        self.assertEqual(original_text, "".join(panel.text for panel in result.panels))
        self.assertTrue(all(panel.panel_type == PanelType.scene for panel in result.panels))

    def test_fixed_original_story_segmentation_requires_requested_count(self) -> None:
        with patch(
            "app.services.llm.call_siliconflow_json",
            return_value={
                "panels": [
                    {"panel_order": 1, "text": "我问他吃饭了没有"},
                    {"panel_order": 2, "text": "他刚回了我一句就累得睡着了"},
                ]
            },
        ) as call_json:
            result = segment_story(
                original_text="我问他吃饭了没有他刚回了我一句就累得睡着了",
                image_count_mode=ImageCountMode.fixed,
                requested_image_count=2,
            )

        user_payload = json.loads(call_json.call_args.kwargs["user_prompt"])
        self.assertIn("必须刚好输出 2 个 panels", user_payload["count_instruction"])
        self.assertEqual(2, len(result.panels))

    def test_original_story_segmentation_rejects_overlong_panel_text(self) -> None:
        overlong_text = "一" * 51
        with patch(
            "app.services.llm.call_siliconflow_json",
            return_value={"panels": [{"panel_order": 1, "text": overlong_text}]},
        ):
            with self.assertRaisesRegex(LLMResponseError, "超过 50 字"):
                segment_story(
                    original_text=overlong_text,
                    image_count_mode=ImageCountMode.auto,
                    requested_image_count=None,
                )

    def test_original_story_segmentation_rejects_non_covering_llm_result(self) -> None:
        with patch(
            "app.services.llm.call_siliconflow_json",
            return_value={"panels": [{"panel_order": 1, "text": "我问他吃饭了"}]},
        ):
            with self.assertRaisesRegex(LLMResponseError, "逐字覆盖原文"):
                segment_story(
                    original_text="我问他吃饭了没有",
                    image_count_mode=ImageCountMode.auto,
                    requested_image_count=None,
                )

    def test_fixed_count_fails_before_llm_when_max_length_is_impossible(self) -> None:
        with patch("app.services.llm.call_siliconflow_json") as call_json:
            with self.assertRaisesRegex(LLMConfigError, "固定图片数量过少"):
                segment_story(
                    original_text="一" * 101,
                    image_count_mode=ImageCountMode.fixed,
                    requested_image_count=2,
                )

        call_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
