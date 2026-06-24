import json
import unittest
from unittest.mock import patch

from app.models.enums import ImageCountMode, PanelType
from app.services.llm import LLMConfigError, LLMResponseError, segment_story


class StorySegmentationTest(unittest.TestCase):
    def test_original_story_segmentation_uses_llm_and_keeps_semantic_chunks(self) -> None:
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
        self.assertEqual({"min": 30, "max": 50}, user_payload["target_panel_text_chars"])
        self.assertIn("自动判断", user_payload["count_instruction"])
        self.assertIn("首要目标是画面单元、情绪转折和叙事节奏自然", call_json.call_args.kwargs["system_prompt"])
        self.assertIn("不要为了凑到 30-50 字", call_json.call_args.kwargs["system_prompt"])
        self.assertIn("煮了一碗面", call_json.call_args.kwargs["system_prompt"])
        self.assertEqual(
            ["我三叔特别的喜欢我是有原因的\n", "他有时候工地夜班干完活回来"],
            [panel.text for panel in result.panels],
        )
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

    def test_original_story_segmentation_allows_light_punctuation_normalization(self) -> None:
        with patch(
            "app.services.llm.call_siliconflow_json",
            return_value={"panels": [{"panel_order": 1, "text": "我问他吃饭了没有。"}]},
        ):
            result = segment_story(
                original_text="我问他吃饭了没有",
                image_count_mode=ImageCountMode.auto,
                requested_image_count=None,
            )

        self.assertEqual("我问他吃饭了没有。", result.panels[0].text)

    def test_auto_original_story_segmentation_refines_fragmented_short_panels(self) -> None:
        original_text = (
            "我三叔特别的喜欢我是有原因的\n"
            "他有时候工地夜班干完活回来\n"
            "我问他吃饭了没有\n"
            "他刚回了我一句就累得睡着了\n"
            "7岁的我还没有灶台高\n"
            "我站在凳子上给他煮了一碗面还放了好多的鸡蛋"
        )
        with patch(
            "app.services.llm.call_siliconflow_json",
            side_effect=[
                {
                    "panels": [
                        {"panel_order": 1, "text": "我三叔特别的喜欢我是有原因的"},
                        {"panel_order": 2, "text": "他有时候工地夜班干完活回来"},
                        {"panel_order": 3, "text": "我问他吃饭了没有"},
                        {"panel_order": 4, "text": "他刚回了我一句就累得睡着了"},
                        {"panel_order": 5, "text": "7岁的我还没有灶台高"},
                        {"panel_order": 6, "text": "我站在凳子上给他煮了一碗面还放了好多的鸡蛋"},
                    ]
                },
                {
                    "panels": [
                        {"panel_order": 1, "text": "我三叔特别的喜欢我是有原因的。他有时候工地夜班干完活回来。"},
                        {"panel_order": 2, "text": "我问他吃饭了没有。他刚回了我一句就累得睡着了。"},
                        {"panel_order": 3, "text": "7岁的我还没有灶台高。我站在凳子上给他煮了一碗面，还放了好多的鸡蛋。"},
                    ]
                },
            ],
        ) as call_json:
            result = segment_story(
                original_text=original_text,
                image_count_mode=ImageCountMode.auto,
                requested_image_count=None,
            )

        self.assertEqual(2, call_json.call_count)
        retry_payload = json.loads(call_json.call_args_list[1].kwargs["user_prompt"])
        self.assertIn("上一次切割结果明显过碎", retry_payload["retry_instruction"])
        self.assertEqual(
            [
                "我三叔特别的喜欢我是有原因的。他有时候工地夜班干完活回来。",
                "我问他吃饭了没有。他刚回了我一句就累得睡着了。",
                "7岁的我还没有灶台高。我站在凳子上给他煮了一碗面，还放了好多的鸡蛋。",
            ],
            [panel.text for panel in result.panels],
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
