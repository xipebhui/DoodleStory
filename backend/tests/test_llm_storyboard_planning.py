import json
import unittest
from unittest.mock import patch

from app.models.enums import ImageCountMode, PanelType
from app.services.llm import LLMResponseError, plan_adapted_story_panels, plan_original_storyboard, plan_storyboard_from_brief


class StoryboardPlanningTest(unittest.TestCase):
    def test_original_storyboard_uses_llm_chunks_and_preserves_text(self) -> None:
        original_text = "今天下雨，我骑车回家。妻子说“慢点骑”。"
        with patch(
            "app.services.llm.call_siliconflow_json",
            return_value={
                "story_title": "雨夜回家",
                "story_hook": "雨夜里的夫妻对话",
                "story_outline": "雨天骑车回家，妻子提醒丈夫慢点。",
                "continuity_plan": {
                    "story_structure": "单一雨天场景",
                    "timeline_segments": [
                        {
                            "label": "当下",
                            "panel_orders": [1, 2],
                            "time_anchor": "雨天",
                            "age_stage_notes": "成年夫妻",
                        }
                    ],
                    "scene_groups": [
                        {
                            "scene_group_id": "scene_rain_road",
                            "panel_orders": [1, 2],
                            "location": "雨天路上",
                            "time_of_day": "傍晚",
                            "weather": "下雨",
                            "stable_environment": "湿漉漉的路面",
                            "stable_props": ["自行车", "雨水"],
                            "continuity_notes": "保持同一路面和雨势",
                        }
                    ],
                    "speaker_map": [
                        {
                            "panel_order": 2,
                            "quote": "慢点骑",
                            "speaker": "妻子",
                            "reason": "原文直接写妻子说",
                        }
                    ],
                    "panel_character_expectations": [
                        {"panel_order": 1, "expected_appearances": ["丈夫成年"]},
                        {"panel_order": 2, "expected_appearances": ["妻子成年"]},
                    ],
                },
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "scene",
                        "story_beat": "今天下雨，我骑车回家。",
                        "visual_prompt": "雨天路上，丈夫骑着自行车回家。",
                        "text_layout": "单页漫画构图",
                        "image_text": {"narration": "今天下雨，我骑车回家。"},
                    },
                    {
                        "panel_order": 2,
                        "panel_type": "scene",
                        "story_beat": "妻子说“慢点骑”。",
                        "visual_prompt": "妻子坐在后座，提醒丈夫说：“慢点骑”。",
                        "text_layout": "单页漫画构图",
                        "image_text": {"narration": "妻子说“慢点骑”。"},
                    },
                ],
            },
        ) as call_json:
            result = plan_original_storyboard(
                original_text=original_text,
                style_prompt="手绘漫画风",
                image_count_mode=ImageCountMode.auto,
                requested_image_count=None,
            )

        user_payload = json.loads(call_json.call_args.kwargs["user_prompt"])
        self.assertEqual(original_text, user_payload["original_text"])
        self.assertIn("自然切分 panels", user_payload["count_instruction"])
        self.assertEqual(original_text, "".join(panel.story_beat for panel in result.panels))
        self.assertEqual("妻子", result.continuity_plan["speaker_map"][0]["speaker"])

    def test_original_storyboard_rejects_changed_text(self) -> None:
        with patch(
            "app.services.llm.call_siliconflow_json",
            return_value={
                "story_title": "雨夜回家",
                "story_hook": "雨夜里的夫妻对话",
                "story_outline": "雨天骑车回家。",
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "scene",
                        "story_beat": "今天下雨，我骑车回家",
                        "visual_prompt": "雨天路上，丈夫骑着自行车回家。",
                        "text_layout": "单页漫画构图",
                        "image_text": {"narration": "今天下雨，我骑车回家"},
                    }
                ],
            },
        ):
            with self.assertRaisesRegex(LLMResponseError, "逐字覆盖原文"):
                plan_original_storyboard(
                    original_text="今天下雨，我骑车回家。",
                    style_prompt="手绘漫画风",
                    image_count_mode=ImageCountMode.auto,
                    requested_image_count=None,
                )

    def test_storyboard_from_brief_uses_requested_count_without_cover(self) -> None:
        with patch(
            "app.services.llm.call_siliconflow_json",
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
            "app.services.llm.call_siliconflow_json",
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


if __name__ == "__main__":
    unittest.main()
