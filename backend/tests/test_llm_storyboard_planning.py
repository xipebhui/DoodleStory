import json
import unittest
from unittest.mock import patch

from app.models.enums import ImageCountMode, PanelType
from app.services.llm import (
    LLMResponseError,
    parse_extracted_storyboard,
    parse_knowledge_plan,
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

    def test_knowledge_plan_uses_llm_to_split_explicit_pages_without_text_fields(self) -> None:
        plan = """第1页|内容
生成一张知识图鉴。主题「自律自控」。
顶部标题区、中部三栏、底部金句全部保留。

第2页：内容
生成一张知识图鉴。主题「及时止损」。
保留左右信息框和路径条。"""

        with patch(
            "app.services.llm.call_lio_json",
            return_value={
                "story_title": "知识图文方案",
                "story_hook": "两页成长知识图鉴。",
                "story_outline": "共拆成 2 页：第1页自律自控；第2页及时止损。",
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "scene",
                        "story_beat": "自律自控",
                        "visual_prompt": "生成一张知识图鉴。主题「自律自控」。顶部标题区、中部三栏、底部金句全部保留。",
                        "text_layout": "顶部标题+中部三栏+底部金句",
                        "image_text": {"title": "自律自控"},
                    },
                    {
                        "panel_order": 2,
                        "panel_type": "scene",
                        "story_beat": "及时止损",
                        "visual_prompt": "生成一张知识图鉴。主题「及时止损」。保留左右信息框和路径条。",
                        "text_layout": "左右信息框",
                        "image_text": {"title": "及时止损"},
                    },
                ],
            },
        ) as call_json:
            result = parse_knowledge_plan(
                plan_text=plan,
                style_prompt="复古知识图鉴风",
                image_count_mode=ImageCountMode.fixed,
                requested_image_count=2,
            )

        self.assertEqual("知识图文方案", result.story_title)
        self.assertEqual([1, 2], [panel.panel_order for panel in result.panels])
        self.assertIn("主题「自律自控」", result.panels[0].visual_prompt)
        self.assertIn("顶部标题区、中部三栏、底部金句全部保留", result.panels[0].visual_prompt)
        self.assertIsNone(result.panels[0].text_layout)
        self.assertIsNone(result.panels[0].image_text.title)
        self.assertIsNone(result.panels[0].image_text.narration)
        user_payload = json.loads(call_json.call_args.kwargs["user_prompt"])
        self.assertIn("必须刚好输出 2 个 panels", user_payload["count_instruction"])
        self.assertEqual(plan, user_payload["plan_text"])
        self.assertEqual("parse_knowledge_plan_v1.md", call_json.call_args.kwargs["prompt_name"])

    def test_knowledge_plan_uses_llm_to_auto_chunk_without_page_markers(self) -> None:
        with patch(
            "app.services.llm.call_lio_json",
            return_value={
                "story_title": "煤气安全知识页",
                "story_hook": "连续知识图鉴内容页。",
                "story_outline": "共拆成 2 页：第1页煤气泄漏；第2页舍财保命。",
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "scene",
                        "story_beat": "煤气泄漏应对",
                        "visual_prompt": "生成连续知识图鉴内容页。主题「煤气泄漏」。正文使用横向内容条，副文字：要立刻关好煤气，再开窗通风，别制造任何明火。",
                        "image_text": {},
                        "text_layout": None,
                    },
                    {
                        "panel_order": 2,
                        "panel_type": "scene",
                        "story_beat": "舍财保命原则",
                        "visual_prompt": "生成连续知识图鉴内容页。主题「舍财保命」。副文字：钱和身外之物都能再赚，命只有一次。",
                        "image_text": {},
                        "text_layout": None,
                    },
                ],
            },
        ):
            result = parse_knowledge_plan(
                plan_text=(
                    "生成连续知识图鉴内容页，复古手绘风。\n"
                    "家里忘记关煤气，反应过来时千万别抽烟或点蚊香\n"
                    "副文字：要立刻关好煤气，再开窗通风，别制造任何明火。\n\n"
                    "遇到不好的情况，舍财保命最重要\n"
                    "副文字：钱和身外之物都能再赚，命只有一次。"
                ),
                style_prompt="复古知识图鉴风",
                image_count_mode=ImageCountMode.auto,
                requested_image_count=None,
            )

        self.assertEqual([1, 2], [panel.panel_order for panel in result.panels])
        self.assertIn("煤气泄漏", result.panels[0].visual_prompt)
        self.assertIn("舍财保命", result.panels[1].visual_prompt)

    def test_knowledge_plan_auto_chunk_splits_structured_positive_prompt_blocks(self) -> None:
        plan = """正向提示词：
生成连续知识图鉴内容页，竖版3:4，复古手绘风，米黄色旧纸底，暖棕色细边框。顶部页眉居中写《煤气与舍财》，黑色粗体大字，页眉下方有暖棕细横线。正文使用2条横向内容条+1条收尾金句栏。每条左侧为完整编号主文字+解释型副文字，右侧为具体场景插画。所有内容条的文字大小、字体、颜色、边框风格保持一致。右侧插画统一为复古手绘细线稿、低饱和暖色。底部页脚居中写“作者：认知方程式”。文字清晰，不乱码，不要3D，不要过度Q版。
家里忘记关煤气，反应过来时千万别抽烟或点蚊香
副文字：要立刻关好煤气，再开窗通风，别制造任何明火。
画面：厨房煤气泄漏，主角一手关煤气阀、一手推开窗户，旁边香烟和蚊香被红叉标记。

遇到不好的情况，舍财保命最重要
副文字：钱和身外之物都能再赚，命只有一次。
画面：夜晚街边遇到抢劫或混乱，主角丢下钱包和背包，快速跑向明亮出口。

收尾金句
副文字：真正的保命常识，不是让你胆小，而是让你在危险靠近前多想一层。
画面：一本合上的安全手册、手电筒、警示牌、急救包，背景有明亮出口。
负向提示词：
乱码，错别字，漏字，顶部标题缺失，底部作者缺失。"""

        with patch(
            "app.services.llm.call_lio_json",
            return_value={
                "story_title": "煤气与舍财",
                "story_hook": "连续知识图鉴内容页。",
                "story_outline": "共拆成 3 页：第1页煤气泄漏；第2页舍财保命；第3页收尾金句。",
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "scene",
                        "story_beat": "煤气泄漏应对",
                        "visual_prompt": "页眉《煤气与舍财》，作者：认知方程式。主题：家里忘记关煤气，反应过来时千万别抽烟或点蚊香。副文字：要立刻关好煤气，再开窗通风，别制造任何明火。画面：厨房煤气泄漏，主角一手关煤气阀、一手推开窗户，旁边香烟和蚊香被红叉标记。复古手绘风，米黄色旧纸底，暖棕色细边框。负向：乱码，错别字，漏字。",
                        "image_text": {},
                        "text_layout": None,
                    },
                    {
                        "panel_order": 2,
                        "panel_type": "scene",
                        "story_beat": "舍财保命原则",
                        "visual_prompt": "页眉《煤气与舍财》，作者：认知方程式。主题：遇到不好的情况，舍财保命最重要。副文字：钱和身外之物都能再赚，命只有一次。画面：夜晚街边遇到抢劫或混乱，主角丢下钱包和背包，快速跑向明亮出口。复古手绘风，米黄色旧纸底，暖棕色细边框。负向：乱码，错别字，漏字。",
                        "image_text": {},
                        "text_layout": None,
                    },
                    {
                        "panel_order": 3,
                        "panel_type": "scene",
                        "story_beat": "收尾金句",
                        "visual_prompt": "页眉《煤气与舍财》，作者：认知方程式。收尾金句：真正的保命常识，不是让你胆小，而是让你在危险靠近前多想一层。画面：一本合上的安全手册、手电筒、警示牌、急救包，背景有明亮出口。复古手绘风，米黄色旧纸底，暖棕色细边框。负向：乱码，错别字，漏字。",
                        "image_text": {},
                        "text_layout": None,
                    },
                ],
            },
        ) as call_json:
            result = parse_knowledge_plan(
                plan_text=plan,
                style_prompt="复古手绘风",
                image_count_mode=ImageCountMode.auto,
                requested_image_count=None,
            )

        system_prompt = call_json.call_args.kwargs["system_prompt"]
        self.assertIn("正向提示词里的页眉、纸张、边框、作者栏", system_prompt)
        self.assertIn("一个独立知识条目通常对应一页", system_prompt)
        self.assertEqual([1, 2, 3], [panel.panel_order for panel in result.panels])
        self.assertIn("煤气", result.panels[0].visual_prompt)
        self.assertIn("舍财保命", result.panels[1].visual_prompt)
        self.assertIn("收尾金句", result.panels[2].story_beat)

    def test_knowledge_plan_fixed_count_mismatch_uses_friendly_error(self) -> None:
        with patch(
            "app.services.llm.call_lio_json",
            return_value={
                "story_title": "知识方案",
                "story_hook": "两页知识图鉴。",
                "story_outline": "共 2 页。",
                "panels": [
                    {
                        "panel_order": 1,
                        "panel_type": "scene",
                        "story_beat": "自律自控",
                        "visual_prompt": "图1：自律自控",
                        "image_text": {},
                    },
                    {
                        "panel_order": 2,
                        "panel_type": "scene",
                        "story_beat": "及时止损",
                        "visual_prompt": "图2：及时止损",
                        "image_text": {},
                    },
                ],
            },
        ):
            with self.assertRaises(LLMResponseError) as raised:
                parse_knowledge_plan(
                    plan_text="图1：自律自控\n图2：及时止损",
                    style_prompt="复古知识图鉴风",
                    image_count_mode=ImageCountMode.fixed,
                    requested_image_count=3,
                )

        self.assertIn("图片解析出的分镜数量（2）和你设置的图片数量（3）不一致", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
