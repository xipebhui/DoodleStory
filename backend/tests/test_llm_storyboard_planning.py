import json
import unittest
from unittest.mock import patch

from app.models.enums import ImageCountMode, PanelType
from app.services.llm import (
    LLMResponseError,
    parse_extracted_storyboard,
    plan_adapted_story_panels,
    plan_storyboard_from_brief,
)


class StoryboardPlanningTest(unittest.TestCase):
    def test_storyboard_from_brief_uses_requested_count_without_cover(self) -> None:
        with patch(
            "app.services.llm.call_lio_json",
            return_value={
                "story_title": "办公室对话",
                "story_hook": "男孩第一次反抗老板",
                "story_outline": "从压迫到反击的三页连续分镜。",
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "cover",
                        "story_beat": "男孩站在办公室门口",
                        "visual_prompt": "男孩站在办公室门口，老板坐在桌后。",
                        "text_layout": "单页漫画构图",
                        "image_text": {"narration": "我第一次走进老板办公室。"},
                    },
                    {
                        "panel_order": 2,
                        "panel_type": "scene",
                        "story_beat": "老板质问男孩",
                        "visual_prompt": "老板拍桌，皱眉质问男孩：“你凭什么？”男孩沉默站在桌前。",
                        "text_layout": "单页漫画构图",
                        "image_text": {},
                    },
                    {
                        "panel_order": 3,
                        "panel_type": "scene",
                        "story_beat": "男孩回应",
                        "visual_prompt": "男孩抬头看向老板，坚定地说：“凭我自己。”",
                        "text_layout": "单页漫画构图",
                        "image_text": {},
                    },
                ],
            },
        ) as call_json:
            result = plan_storyboard_from_brief(
                brief_text="老板和男孩办公室对话",
                style_prompt="黑白漫画风",
                image_count_mode=ImageCountMode.fixed,
                requested_image_count=3,
            )

        user_payload = json.loads(call_json.call_args.kwargs["user_prompt"])
        self.assertIn("必须刚好输出 3 个 panels", user_payload["count_instruction"])
        self.assertNotIn("封面", user_payload["count_instruction"])
        self.assertEqual([1, 2, 3], [panel.panel_order for panel in result.panels])
        self.assertTrue(all(panel.panel_type == PanelType.scene for panel in result.panels))

    def test_adapted_story_panels_are_normalized_to_scene(self) -> None:
        with patch(
            "app.services.llm.call_lio_json",
            return_value={
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "cover",
                        "text": "暴雨夜，阿宁捡到钥匙。",
                        "narration_text": "暴雨夜，阿宁捡到钥匙。",
                        "dialogue_text": None,
                    }
                ]
            },
        ) as call_json:
            result = plan_adapted_story_panels(
                title="灯塔钥匙",
                hook="阿宁点亮灯塔",
                adapted_story="暴雨夜，阿宁在旧灯塔下捡到钥匙。",
                image_count_mode=ImageCountMode.auto,
                requested_image_count=None,
            )

        user_payload = json.loads(call_json.call_args.kwargs["user_prompt"])
        self.assertIn("不要额外生成封面", user_payload["count_instruction"])
        self.assertEqual(PanelType.scene, result.panels[0].panel_type)

    def test_extracted_storyboard_validation_error_hides_internal_schema_fields(self) -> None:
        with patch(
            "app.services.llm.call_lio_json",
            return_value={
                "story_hook": "女孩在操场自拍",
                "story_outline": "从教室到操场的三页分镜。",
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "scene",
                        "story_beat": "教室回头",
                        "visual_prompt": "教室里男生回头看向女生。",
                        "image_text": {"narration": "我和我对象是大学同班同学"},
                    }
                ],
            },
        ):
            with self.assertRaises(LLMResponseError) as raised:
                parse_extracted_storyboard(
                    extracted_text="第1页：教室里男生回头看向女生。",
                    style_prompt="黑白漫画风",
                    image_count_mode=ImageCountMode.auto,
                    requested_image_count=None,
                )

        message = str(raised.exception)
        self.assertIn("内容提取分镜结构化失败", message)
        self.assertNotIn("story_title", message)
        self.assertNotIn("Field required", message)

    def test_extracted_storyboard_count_mismatch_uses_friendly_error(self) -> None:
        with patch(
            "app.services.llm.call_lio_json",
            return_value={
                "error": "固定图片数量要求为 12，但输入共检测到 13 页（第1页至第13页），页数不匹配，无法按规则输出。",
            },
        ):
            with self.assertRaises(LLMResponseError) as raised:
                parse_extracted_storyboard(
                    extracted_text="第1页：开场。\n第13页：结尾。",
                    style_prompt="黑白漫画风",
                    image_count_mode=ImageCountMode.fixed,
                    requested_image_count=12,
                )

        message = str(raised.exception)
        self.assertIn("图片解析出的分镜数量（13）和你设置的图片数量（12）不一致", message)
        self.assertIn("请把图片数量改为 13", message)
        self.assertNotIn("内容提取分镜结构化失败", message)
        self.assertNotIn("Field required", message)

    def test_extracted_storyboard_panel_result_count_mismatch_uses_friendly_error(self) -> None:
        with patch(
            "app.services.llm.call_lio_json",
            return_value={
                "story_title": "三页故事",
                "story_hook": "开场到结尾",
                "story_outline": "三页连续分镜。",
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "scene",
                        "story_beat": "开场",
                        "visual_prompt": "角色站在门口。",
                        "text_layout": "单页漫画构图",
                        "image_text": {},
                    },
                    {
                        "panel_order": 2,
                        "panel_type": "scene",
                        "story_beat": "推进",
                        "visual_prompt": "角色走进房间。",
                        "text_layout": "单页漫画构图",
                        "image_text": {},
                    },
                    {
                        "panel_order": 3,
                        "panel_type": "scene",
                        "story_beat": "结尾",
                        "visual_prompt": "角色坐在桌前。",
                        "text_layout": "单页漫画构图",
                        "image_text": {},
                    },
                ],
            },
        ):
            with self.assertRaises(LLMResponseError) as raised:
                parse_extracted_storyboard(
                    extracted_text="第1页：开场。\n第2页：推进。\n第3页：结尾。",
                    style_prompt="黑白漫画风",
                    image_count_mode=ImageCountMode.fixed,
                    requested_image_count=2,
                )

        message = str(raised.exception)
        self.assertIn("图片解析出的分镜数量（3）和你设置的图片数量（2）不一致", message)


if __name__ == "__main__":
    unittest.main()
