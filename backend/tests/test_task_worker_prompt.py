import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from app.models.entities import (
    FileAsset,
    GenerationTask,
    TaskCharacter,
    TaskCharacterAppearance,
    TaskPanel,
    TaskPanelCharacterAppearance,
    TaskStyleReferenceImage,
)
from app.models.enums import (
    FileAssetPurpose,
    ImageCountMode,
    PanelType,
    StorageBackend,
    StoryInputMode,
    StyleReferenceMode,
    WorkflowStatus,
)
from app.services.image_generation import (
    GeneratedImageFile,
    ImageProviderConfigError,
    ImageProviderResponseError,
    ImageReference,
)
from app.services.llm import LLMResponseError, compose_final_image_prompts
from app.services.task_worker import (
    GenerationReferencePack,
    PreparedPanelImageRequest,
    build_adapted_story_final_prompt,
    build_generation_reference_pack,
    build_original_story_final_prompt,
    build_panel_final_prompt,
    final_prompt_with_aspect_ratio_prefix,
    final_prompt_with_explicit_style,
    normalized_person_reference_lines,
    normalized_style_reference_lines,
    generate_panel_image_request,
    is_policy_blocked_image_error,
    normalized_task_reference_lines,
    person_reference_block,
    sanitize_compiled_final_prompt,
    style_reference_block,
    task_reference_block,
    trim_generation_reference_pack_for_model,
)
from app.services.character_references import build_character_style_reference_pack


class TaskWorkerPromptTest(unittest.TestCase):
    def test_compose_final_image_prompts_returns_llm_final_prompts(self) -> None:
        with patch(
            "app.services.llm.call_siliconflow_json",
            return_value={
                "panels": [
                    {
                        "panel_order": 1,
                        "final_prompt": "第 1 页（单页 | 3:4）\n男生保持黄色上衣，女生保持橄榄绿上衣。",
                        "consistency_notes": ["分镜里的蓝色裙子被角色外观锁定改为橄榄绿上衣"],
                    }
                ]
            },
        ) as call_json:
            result = compose_final_image_prompts(
                task_payload={
                    "story_input_mode": "adapted",
                    "aspect_ratio": "3:4",
                    "style_reference_mode": "prompt",
                    "style_prompt": "粗糙手绘漫画风",
                },
                characters=[
                    {
                        "character_key": "fixed_1",
                        "name": "女生",
                        "source_type": "user_fixed_character",
                        "description": "橄榄绿上衣，深色下装",
                        "appearances": [],
                    }
                ],
                panels=[
                    {
                        "panel_order": 1,
                        "visual_prompt": "女生穿蓝色裙子坐在长椅上",
                        "image_text": {"narration": "恋爱后期的无奈瞬间"},
                    }
                ],
            )

        self.assertEqual(1, result.panels[0].panel_order)
        self.assertIn("橄榄绿上衣", result.panels[0].final_prompt)
        self.assertEqual(
            "compose_final_image_prompts_v1.md",
            call_json.call_args.kwargs["prompt_name"],
        )
        self.assertEqual(0.2, call_json.call_args.kwargs["temperature"])

    def test_compose_final_image_prompts_rejects_panel_order_mismatch(self) -> None:
        with patch(
            "app.services.llm.call_siliconflow_json",
            return_value={"panels": [{"panel_order": 2, "final_prompt": "第 2 页"}]},
        ) as call_json:
            with self.assertRaises(LLMResponseError):
                compose_final_image_prompts(
                    task_payload={"aspect_ratio": "3:4"},
                    characters=[],
                    panels=[{"panel_order": 1, "visual_prompt": "女孩在窗边读书"}],
                )
        self.assertEqual(3, call_json.call_count)

    def test_compose_final_image_prompts_retries_panel_order_mismatch(self) -> None:
        with patch(
            "app.services.llm.call_siliconflow_json",
            side_effect=[
                {
                    "panels": [
                        {"panel_order": 2, "final_prompt": "第 2 页"},
                        {"panel_order": 1, "final_prompt": "第 1 页"},
                    ]
                },
                {
                    "panels": [
                        {"panel_order": 1, "final_prompt": "第 1 页"},
                        {"panel_order": 2, "final_prompt": "第 2 页"},
                    ]
                },
            ],
        ) as call_json:
            result = compose_final_image_prompts(
                task_payload={"aspect_ratio": "3:4"},
                characters=[],
                panels=[
                    {"panel_order": 1, "visual_prompt": "女孩在窗边读书"},
                    {"panel_order": 2, "visual_prompt": "女孩走出教室"},
                ],
            )

        self.assertEqual([1, 2], [panel.panel_order for panel in result.panels])
        self.assertEqual(2, call_json.call_count)
        retry_payload = call_json.call_args_list[1].kwargs["user_prompt"]
        self.assertIn("retry_instruction", retry_payload)
        self.assertIn("panel_order 必须依次为 [1, 2]", retry_payload)

    def test_final_prompt_uses_visual_prompt_dialogue_once(self) -> None:
        final_prompt = build_adapted_story_final_prompt(
            aspect_ratio="3:4",
            visual_prompt="主画面+右下角分镜布局，父亲伸手阻止孩子，焦急地对孩子说：“别拿这个乱玩，拿过来。”孩子哭着跑开。",
            story_beat="男主焦急地阻止儿子，孩子被吓哭。",
            panel_type=PanelType.scene,
            image_text={
                "title": None,
                "narration": "我急得朝他吼了一下\n他吓的哭了出来\n去喊我老婆",
                "inner_os": None,
                "emphasis": None,
            },
            reference_notes=["男主角/丈夫参考（参考图1）", "儿子参考（参考图2）"],
            text_layout="主画面+右下角分镜",
        )

        self.assertIn("当前分镜：", final_prompt)
        self.assertNotIn("第1页", final_prompt)
        self.assertIn("【分格】主画面+右下角分镜", final_prompt)
        self.assertIn("父亲伸手阻止孩子，焦急地对孩子说：“别拿这个乱玩，拿过来。”", final_prompt)
        self.assertIn("旁白：我急得朝他吼了一下\n他吓的哭了出来\n去喊我老婆", final_prompt)
        self.assertIn("对话：无", final_prompt)
        self.assertIn("内心OS：无", final_prompt)
        self.assertIn("字段名只用于理解分镜结构", final_prompt)
        self.assertIn("对白出现在对应人物附近的对白气泡中", final_prompt)
        self.assertIn("不要在旁白框里重复", final_prompt)
        self.assertNotIn("分格/多栏布局：", final_prompt)
        self.assertNotIn("不要添加指定文字之外", final_prompt)
        self.assertNotIn("Logo 或水印", final_prompt)
        self.assertNotIn("不要画成对白气泡", final_prompt)

    def test_final_prompt_includes_style_prompt_when_provided(self) -> None:
        final_prompt = build_adapted_story_final_prompt(
            aspect_ratio="3:4",
            visual_prompt="一家人坐在餐桌边，画面温暖。",
            story_beat="家庭日常对话。",
            panel_type=PanelType.scene,
            image_text={"narration": "晚饭时间到了"},
            style_prompt="低饱和手绘漫画风，细线条，浅色水彩，中文手写字要清晰偏大。",
        )

        self.assertIn("风格提示词（必须直接用于本张图", final_prompt)
        self.assertIn("低饱和手绘漫画风，细线条，浅色水彩，中文手写字要清晰偏大。", final_prompt)
        self.assertTrue(final_prompt.startswith("画面比例：3:4"))
        self.assertLess(final_prompt.index("画面比例：3:4"), final_prompt.index("风格提示词"))

    def test_multi_panel_narration_is_constrained_to_single_caption(self) -> None:
        final_prompt = build_adapted_story_final_prompt(
            aspect_ratio="3:4",
            visual_prompt=(
                "漫画页，上下两格，阅读顺序从上到下。上格：女主在烈日下发传单。"
                "下格：女主隔着玻璃看小孩吃冰淇淋。"
            ),
            story_beat="女主在烈日下发传单，羡慕别人家的孩子吃冰淇淋。",
            panel_type=PanelType.scene,
            image_text={
                "narration": "大太阳底下，我发着传单，\n隔着玻璃看别人家的小幼孩吃冰淇淋。",
            },
            text_layout="上下两格",
        )

        self.assertIn("所有指定文字只出现一次", final_prompt)
        self.assertIn("整页旁白只使用一个旁白框", final_prompt)
        self.assertIn("不要在上格、下格或不同分栏里重复放置同一段旁白", final_prompt)
        self.assertIn("【分格】上下两格", final_prompt)
        self.assertIn("旁白：大太阳底下，我发着传单，\n隔着玻璃看别人家的小幼孩吃冰淇淋。", final_prompt)
        self.assertIn("画面必须采用上下两格。", final_prompt)
        self.assertNotIn("分格/多栏布局：", final_prompt)

    def test_single_page_layout_block_is_omitted_from_final_prompt(self) -> None:
        final_prompt = build_adapted_story_final_prompt(
            aspect_ratio="3:4",
            visual_prompt="漫画页，单页构图。女孩奔跑着回头。",
            story_beat="女孩逃跑时回头提醒同伴。",
            panel_type=PanelType.scene,
            image_text={
                "narration": "嘴里还一直喊：“别被追上！你们太小了！”",
            },
            text_layout="单页漫画构图",
        )

        self.assertIn("【分格】单页", final_prompt)
        self.assertIn("旁白：嘴里还一直喊：“别被追上！你们太小了！”", final_prompt)
        self.assertNotIn("分格/多栏布局：", final_prompt)
        self.assertNotIn("画面必须采用单页漫画构图", final_prompt)

    def test_original_story_final_prompt_uses_structured_storyboard_block(self) -> None:
        final_prompt = build_original_story_final_prompt(
            aspect_ratio="3:4",
            visual_prompt="女生坐在教室靠窗位置低头看书，男生坐在右侧课桌前偷偷看她。",
            exact_text="我高中的时候暗恋一个女生\n而我当时只是一个自卑的小胖子...",
            panel_order=3,
        )

        self.assertIn("当前分镜：", final_prompt)
        self.assertNotIn("第3页", final_prompt)
        self.assertIn("【分格】单页", final_prompt)
        self.assertIn("画面：女生坐在教室靠窗位置低头看书，男生坐在右侧课桌前偷偷看她。", final_prompt)
        self.assertIn("旁白：我高中的时候暗恋一个女生\n而我当时只是一个自卑的小胖子...", final_prompt)
        self.assertIn("对话：无", final_prompt)
        self.assertIn("内心OS：无", final_prompt)
        self.assertIn("逐字一致", final_prompt)
        self.assertIn("不要把“画面”“旁白”“对话”“内心OS”等字段名画进图片", final_prompt)

    def test_panel_final_prompt_keeps_style_prompt_in_image_reference_mode(self) -> None:
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.original,
            image_count_mode=ImageCountMode.auto,
            style_id="style",
            style_name_snapshot="参考图风格",
            style_prompt_snapshot="黑白线稿，白色背景，杂乱手绘线条。",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.image,
        )
        panel = TaskPanel(panel_order=1, panel_type=PanelType.scene, original_text_segment="原文")

        final_prompt = build_panel_final_prompt(
            task=task,
            panel=panel,
            visual_prompt="女孩在窗边读书。",
            image_text={"narration": "原文"},
            reference_notes=["风格参考（参考图1）"],
        )

        self.assertIn("风格参考（参考图1）", final_prompt)
        self.assertIn("风格提示词（必须直接用于本张图", final_prompt)
        self.assertIn("黑白线稿，白色背景，杂乱手绘线条。", final_prompt)
        self.assertIn("【分格】单页", final_prompt)
        self.assertIn("旁白：原文", final_prompt)

    def test_llm_final_prompt_adds_explicit_style_prompt_in_prompt_mode(self) -> None:
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.adapted,
            image_count_mode=ImageCountMode.auto,
            style_id="style",
            style_name_snapshot="手绘风",
            style_prompt_snapshot="低饱和手绘漫画风，人物比例极简，中文手写字清晰偏大。",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.prompt,
        )

        final_prompt = final_prompt_with_explicit_style(
            task,
            "第 1 页（单页 | 3:4）\n男生保持黄色衬衫，女生保持橄榄绿上衣。",
        )

        self.assertTrue(final_prompt.startswith("画面比例：3:4。必须严格按 3:4 宽高比构图和出图"))
        self.assertIn("风格提示词（必须直接用于本张图", final_prompt)
        self.assertIn("低饱和手绘漫画风，人物比例极简，中文手写字清晰偏大。", final_prompt)
        self.assertIn("风格执行优先级：人物参考外观锁定 > 当前剧情动作/情绪", final_prompt)
        self.assertIn("最终画面指令：", final_prompt)
        self.assertIn("男生保持黄色衬衫，女生保持橄榄绿上衣。", final_prompt)
        self.assertLess(final_prompt.index("画面比例：3:4"), final_prompt.index("风格提示词"))
        self.assertLess(final_prompt.index("风格提示词"), final_prompt.index("最终画面指令"))

    def test_prompt_mode_final_prompt_includes_character_reference_mapping(self) -> None:
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.original,
            image_count_mode=ImageCountMode.auto,
            style_id="style",
            style_name_snapshot="手绘风",
            style_prompt_snapshot="低饱和手绘漫画风，中文手写字清晰偏大。",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.prompt,
        )

        final_prompt = final_prompt_with_explicit_style(
            task,
            "青年男性（我）站在工厂门口。",
            reference_notes=["固定角色参考（参考图1）：我\n外观锁定：短发，工装，疲惫感"],
        )

        self.assertIn("人物参考（第一优先级，必须严格执行）：", final_prompt)
        self.assertIn("人物外观参考图1（我）", final_prompt)
        self.assertIn("以上人物参考图已随请求传入；每张图是对应人物的唯一外观依据。", final_prompt)
        self.assertIn("不能改变人物身份和外形锚点", final_prompt)
        self.assertIn("风格提示词（必须直接用于本张图", final_prompt)
        self.assertIn("低饱和手绘漫画风，中文手写字清晰偏大。", final_prompt)
        self.assertLess(final_prompt.index("人物参考"), final_prompt.index("风格提示词"))
        self.assertLess(final_prompt.index("风格提示词"), final_prompt.index("最终画面指令"))

    def test_aspect_ratio_prefix_is_not_duplicated(self) -> None:
        final_prompt = final_prompt_with_aspect_ratio_prefix(
            "3:4",
            "画面比例：3:4。必须严格按 3:4 宽高比构图和出图。\n\n第 1 页\n女孩在窗边读书。",
        )

        self.assertEqual(1, final_prompt.count("画面比例：3:4"))

    def test_llm_final_prompt_adds_isolated_style_prompt_in_image_mode(self) -> None:
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.adapted,
            image_count_mode=ImageCountMode.auto,
            style_id="style",
            style_name_snapshot="参考图风格",
            style_prompt_snapshot="黑白线稿，白色背景，杂乱手绘线条。",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.image,
        )

        final_prompt = final_prompt_with_explicit_style(
            task,
            "第 1 页\n女孩在窗边读书。",
            reference_notes=["风格参考（参考图1）"],
        )

        self.assertIn("画面比例：3:4。必须严格按 3:4 宽高比构图和出图", final_prompt)
        self.assertNotIn("人物参考（第一优先级", final_prompt)
        self.assertIn("风格参考（仅控制画风，不代表人物身份）：", final_prompt)
        self.assertIn("风格参考（图1）", final_prompt)
        self.assertIn("风格提示词（必须直接用于本张图", final_prompt)
        self.assertIn("黑白线稿，白色背景，杂乱手绘线条。", final_prompt)
        self.assertIn("第 1 页\n女孩在窗边读书。", final_prompt)
        self.assertLess(final_prompt.index("风格参考"), final_prompt.index("风格提示词"))
        self.assertLess(final_prompt.index("风格提示词"), final_prompt.index("最终画面指令"))

    def test_image_mode_final_prompt_appends_standard_task_reference_block(self) -> None:
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.adapted,
            image_count_mode=ImageCountMode.auto,
            style_id="style",
            style_name_snapshot="极简黑白图片参考",
            style_prompt_snapshot="极简黑白；黑白线稿；白色或浅灰留白背景；不要暖色纸张底色。",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.image,
        )
        final_prompt = final_prompt_with_explicit_style(
            task,
            (
                "第 9 页（单页 | 画面比例 3:4）\n"
                "画面并置两个时空的意象。\n"
                "整体风格：参考图2的极简黑白风格。角色外观参考图1（三叔）。\n"
                "整体色调/风格：室内，温暖与疲惫的对比。"
            ),
            reference_notes=[
                "固定角色参考（参考图1）：三叔\n外观锁定：成年男性，建筑工人体态",
                "风格参考（参考图2）",
            ],
        )

        self.assertTrue(final_prompt.startswith("画面比例：3:4。必须严格按 3:4 宽高比构图和出图"))
        self.assertIn("人物参考（第一优先级，必须严格执行）：", final_prompt)
        self.assertIn("人物外观参考图1（三叔）", final_prompt)
        self.assertIn("风格参考（仅控制画风，不代表人物身份）：", final_prompt)
        self.assertIn("风格参考（图2）", final_prompt)
        self.assertLess(final_prompt.index("人物参考"), final_prompt.index("风格参考"))
        self.assertLess(final_prompt.index("风格参考"), final_prompt.index("风格提示词"))
        self.assertIn("风格提示词（必须直接用于本张图", final_prompt)
        self.assertIn("极简黑白；黑白线稿；白色或浅灰留白背景；不要暖色纸张底色。", final_prompt)
        self.assertIn("以上人物参考图已随请求传入", final_prompt)
        self.assertIn("不代表任何人物身份或外观", final_prompt)
        self.assertNotIn("禁止米黄色、黄色、暖色、棕色、复古纸色", final_prompt)
        self.assertNotIn("参考图2的极简黑白风格", final_prompt)
        self.assertNotIn("整体风格：", final_prompt)
        self.assertNotIn("整体色调/风格：", final_prompt)

    def test_last_panel_real_photo_final_prompt_overrides_task_style(self) -> None:
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.extracted_storyboard,
            image_count_mode=ImageCountMode.auto,
            use_character_references=True,
            last_panel_real_photo=True,
            style_id="style",
            style_name_snapshot="极简黑白图片参考",
            style_prompt_snapshot="极简黑白；黑白线稿；白色背景；手绘漫画风。",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.image,
        )

        final_prompt = final_prompt_with_explicit_style(
            task,
            "女生在夜间操场自拍，穿白色T恤，抱着一束红玫瑰。",
            reference_notes=["风格参考（参考图1）"],
            force_real_photo=True,
        )

        self.assertIn("最后一张真人图片", final_prompt)
        self.assertIn("真实摄影照片", final_prompt)
        self.assertIn("真实人物、真实环境、真实光线", final_prompt)
        self.assertIn("不要生成漫画、手绘、绘本、水彩、线稿", final_prompt)
        self.assertIn("女生在夜间操场自拍", final_prompt)
        self.assertNotIn("人物参考（第一优先级", final_prompt)
        self.assertNotIn("风格参考（图1）", final_prompt)
        self.assertNotIn("风格提示词（必须直接用于本张图", final_prompt)
        self.assertNotIn("极简黑白；黑白线稿；白色背景；手绘漫画风。", final_prompt)

    def test_reference_blocks_normalize_person_and_style_notes(self) -> None:
        person_lines = normalized_person_reference_lines(
            [
                "固定角色参考（参考图1）：三叔\n外观锁定：成年男性，建筑工人体态",
                "风格参考（参考图2）",
            ]
        )
        style_lines = normalized_style_reference_lines(
            [
                "固定角色参考（参考图1）：三叔\n外观锁定：成年男性，建筑工人体态",
                "风格参考（参考图2）",
            ]
        )
        task_lines = normalized_task_reference_lines(
            [
                "固定角色参考（参考图1）：三叔\n外观锁定：成年男性，建筑工人体态",
                "风格参考（参考图2）",
            ]
        )

        self.assertEqual(["人物外观参考图1（三叔）"], person_lines)
        self.assertEqual(["风格参考（图2）"], style_lines)
        self.assertEqual(["人物外观参考图1（三叔）", "风格参考（图2）"], task_lines)
        person_block = person_reference_block([
            "固定角色参考（参考图1）：三叔\n外观锁定：成年男性，建筑工人体态",
            "风格参考（参考图2）",
        ])
        style_block = style_reference_block([
            "固定角色参考（参考图1）：三叔\n外观锁定：成年男性，建筑工人体态",
            "风格参考（参考图2）",
        ])
        reference_block = task_reference_block([
            "固定角色参考（参考图1）：三叔\n外观锁定：成年男性，建筑工人体态",
            "风格参考（参考图2）",
        ])
        self.assertIsNotNone(person_block)
        self.assertIsNotNone(style_block)
        self.assertIsNotNone(reference_block)
        self.assertIn("人物参考（第一优先级，必须严格执行）：", person_block)
        self.assertIn("人物外观参考图1（三叔）", person_block)
        self.assertNotIn("风格参考（图2）", person_block)
        self.assertIn("风格参考（仅控制画风，不代表人物身份）：", style_block)
        self.assertIn("风格参考（图2）", style_block)
        self.assertNotIn("人物外观参考图1（三叔）", style_block)
        self.assertIn("人物参考（第一优先级，必须严格执行）：", reference_block)
        self.assertIn("人物外观参考图1（三叔）", reference_block)
        self.assertIn("风格参考（仅控制画风，不代表人物身份）：", reference_block)
        self.assertIn("风格参考（图2）", reference_block)
        self.assertNotIn("当前风格提示", reference_block)

    def test_sanitize_compiled_final_prompt_removes_text_type_labels(self) -> None:
        final_prompt = sanitize_compiled_final_prompt(
            (
                "第1页（单页 | 3:4）\n"
                "画面为夜晚街道，女孩扶着喝醉的男孩回家。\n"
                "【文字】\n"
                "旁白：19岁的我扶着喝多了的24岁的他回家，\n"
                "整体色调/风格：竖版绘本漫画风。"
            ),
            {
                "title": None,
                "narration": "19岁的我扶着喝多了的24岁的他回家，",
                "dialogue": None,
                "inner_os": None,
                "emphasis": None,
            },
        )

        self.assertIn("在留白文字区写入「19岁的我扶着喝多了的24岁的他回家，」", final_prompt)
        self.assertNotIn("第1页", final_prompt)
        self.assertNotIn("旁白：19岁的我扶着喝多了的24岁的他回家，", final_prompt)
        self.assertIn("整体色调/风格：竖版绘本漫画风。", final_prompt)

    def test_sanitize_compiled_final_prompt_removes_page_number_instruction(self) -> None:
        final_prompt = sanitize_compiled_final_prompt(
            (
                "当前单图（单页 | 3:4）\n"
                "画面为孩子站在凳子上煮面，三叔在旁边睡着。\n"
                "在右下角写入「第 2 页」。\n"
                "【文字】\n"
                "旁白：他刚回了我一句就累得睡着了。"
            ),
            {
                "title": None,
                "narration": "他刚回了我一句就累得睡着了。",
                "dialogue": None,
                "inner_os": None,
                "emphasis": None,
            },
        )

        self.assertNotIn("第 2 页", final_prompt)
        self.assertNotIn("右下角", final_prompt)
        self.assertIn("在留白文字区写入「他刚回了我一句就累得睡着了。」", final_prompt)

    def test_generation_reference_pack_orders_character_before_style_reference(self) -> None:
        character_asset = FileAsset(
            purpose=FileAssetPurpose.character_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="characters/zhangsan.png",
            public_url="https://cdn.example.com/characters/zhangsan.png",
            content_type="image/png",
            byte_size=10,
        )
        style_asset = FileAsset(
            purpose=FileAssetPurpose.style_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="styles/watercolor.png",
            public_url="https://cdn.example.com/styles/watercolor.png",
            content_type="image/png",
            byte_size=10,
        )
        character = TaskCharacter(character_key="char_1", name="张三", description="主角")
        appearance = TaskCharacterAppearance(
            appearance_key="char_1_adult",
            status=WorkflowStatus.succeeded,
            reference_image=character_asset,
        )
        appearance.character = character
        panel = TaskPanel(panel_order=1, panel_type=PanelType.scene, original_text_segment="原文")
        panel.character_appearances = [
            TaskPanelCharacterAppearance(
                reference_order=1,
                appearance=appearance,
            )
        ]
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.original,
            image_count_mode=ImageCountMode.auto,
            use_character_references=True,
            style_id="style",
            style_name_snapshot="参考图风格",
            style_prompt_snapshot="手绘风",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.image,
        )
        task.style_reference_images = [
            TaskStyleReferenceImage(reference_order=1, asset=style_asset),
        ]

        pack = build_generation_reference_pack(task, panel)

        self.assertEqual(
            [
                "https://cdn.example.com/characters/zhangsan.png",
                "https://cdn.example.com/styles/watercolor.png",
            ],
            [reference.url for reference in pack.references],
        )
        self.assertEqual("风格参考（参考图2）", pack.notes[1])
        self.assertIn("固定角色参考（参考图1）：张三", pack.notes[0])
        self.assertIn("外观锁定：主角", pack.notes[0])
        self.assertIn("固定角色身份 > 当前剧情动作/情绪 > 风格表现方式 > 风格模板默认人物外观", pack.notes[0])
        self.assertEqual(1, pack.character_reference_count)
        self.assertEqual(1, pack.style_reference_count)

    def test_last_panel_real_photo_reference_pack_is_empty_for_last_panel(self) -> None:
        character_asset = FileAsset(
            purpose=FileAssetPurpose.character_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="characters/zhangsan.png",
            public_url="https://cdn.example.com/characters/zhangsan.png",
            content_type="image/png",
            byte_size=10,
        )
        style_asset = FileAsset(
            purpose=FileAssetPurpose.style_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="styles/watercolor.png",
            public_url="https://cdn.example.com/styles/watercolor.png",
            content_type="image/png",
            byte_size=10,
        )
        character = TaskCharacter(character_key="char_1", name="张三", description="主角")
        appearance = TaskCharacterAppearance(
            appearance_key="char_1_adult",
            status=WorkflowStatus.succeeded,
            reference_image=character_asset,
        )
        appearance.character = character
        first_panel = TaskPanel(panel_order=1, panel_type=PanelType.scene, original_text_segment="前文")
        last_panel = TaskPanel(panel_order=2, panel_type=PanelType.scene, original_text_segment="最后一张自拍")
        last_panel.character_appearances = [
            TaskPanelCharacterAppearance(
                reference_order=1,
                appearance=appearance,
            )
        ]
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.extracted_storyboard,
            image_count_mode=ImageCountMode.auto,
            use_character_references=True,
            last_panel_real_photo=True,
            style_id="style",
            style_name_snapshot="参考图风格",
            style_prompt_snapshot="手绘风",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.image,
        )
        task.panels = [first_panel, last_panel]
        task.style_reference_images = [
            TaskStyleReferenceImage(reference_order=1, asset=style_asset),
        ]

        pack = build_generation_reference_pack(task, last_panel)

        self.assertEqual([], pack.references)
        self.assertEqual(0, pack.character_reference_count)
        self.assertEqual(0, pack.style_reference_count)
        self.assertIn("最后一张真人图片", pack.notes[0])

    def test_generation_reference_pack_rejects_missing_task_style_reference_asset(self) -> None:
        panel = TaskPanel(panel_order=1, panel_type=PanelType.scene, original_text_segment="原文")
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.original,
            image_count_mode=ImageCountMode.auto,
            use_character_references=False,
            style_id="style",
            style_name_snapshot="参考图风格",
            style_prompt_snapshot="手绘风",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.image,
        )
        task.style_reference_images = [
            TaskStyleReferenceImage(reference_order=1, asset_id="missing_asset"),
        ]

        with self.assertRaisesRegex(ImageProviderConfigError, "任务风格参考图快照缺少资产"):
            build_generation_reference_pack(task, panel)

    def test_character_style_reference_pack_uses_task_snapshot_references(self) -> None:
        style_asset = FileAsset(
            purpose=FileAssetPurpose.style_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="styles/minimal.png",
            public_url="https://cdn.example.com/styles/minimal.png",
            content_type="image/png",
            byte_size=10,
        )
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.original,
            image_count_mode=ImageCountMode.auto,
            style_id="style",
            style_name_snapshot="极简黑白图片参考",
            style_prompt_snapshot="极简黑白",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="3:4",
            style_reference_mode_snapshot=StyleReferenceMode.image,
        )
        task.style_reference_images = [
            TaskStyleReferenceImage(reference_order=1, asset=style_asset),
        ]

        pack = build_character_style_reference_pack(task)

        self.assertEqual(["https://cdn.example.com/styles/minimal.png"], [reference.url for reference in pack.references])
        self.assertEqual(["风格参考（参考图1）"], pack.notes)
        self.assertEqual(1, pack.style_count)

    def test_generation_reference_pack_trims_extra_references_and_notes_for_model(self) -> None:
        pack = GenerationReferencePack(
            references=[
                ImageReference(url=f"https://cdn.example.com/reference-{index}.png") for index in range(1, 6)
            ],
            notes=[f"参考图{index}" for index in range(1, 6)],
            character_reference_count=4,
            style_reference_count=1,
        )

        trimmed = trim_generation_reference_pack_for_model(pack, "gpt-image-2")

        self.assertEqual(
            [
                "https://cdn.example.com/reference-1.png",
                "https://cdn.example.com/reference-2.png",
                "https://cdn.example.com/reference-3.png",
                "https://cdn.example.com/reference-4.png",
            ],
            [reference.url for reference in trimmed.references],
        )
        self.assertEqual(["参考图1", "参考图2", "参考图3", "参考图4"], trimmed.notes)
        self.assertEqual(4, trimmed.character_reference_count)
        self.assertEqual(0, trimmed.style_reference_count)

    def test_google_policy_blocked_error_rewrites_prompt_with_same_model_and_references(self) -> None:
        blocked_error = ImageProviderResponseError(
            "图片 Provider 请求失败：HTTP 400 {\"error\":{\"message\":\"Unable to show the generated image. "
            "The image was filtered out because it violated Google's Generative AI Prohibited Use policy\"}}"
        )
        generated = GeneratedImageFile(
            storage_backend=StorageBackend.local,
            storage_key="generated_image/test.jpg",
            byte_size=123,
            checksum_sha256="hash",
            content_type="image/jpeg",
            original_filename="generated-image.jpg",
            provider_request_id="baidu-request",
            public_url=None,
        )
        request = PreparedPanelImageRequest(
            panel_id="panel-1",
            panel_order=9,
            image_id="image-1",
            final_prompt="画一个倔强说不疼的小女孩",
            references=[ImageReference(url="https://cdn.example.com/person.jpg")],
            reference_count=1,
            character_reference_count=1,
            style_reference_count=0,
        )

        with patch("app.services.task_worker.generate_xg_image", side_effect=[blocked_error, generated]) as generate, patch(
            "app.services.task_worker.rewrite_policy_blocked_image_prompt",
            return_value=SimpleNamespace(
                final_prompt="画一个眼眶含泪但倔强微笑的小女孩，避免描述伤害动作",
                change_summary="把疼痛表达改成眼眶含泪和倔强微笑的中性视觉状态",
            ),
        ) as rewrite:
            result = generate_panel_image_request(
                task_id="task-1",
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
                request=request,
            )

        self.assertIs(result.generated, generated)
        self.assertIsNone(result.error)
        rewritten_prompt = (
            "画面比例：3:4。必须严格按 3:4 宽高比构图和出图，不要生成横竖方向或比例不一致的画面。\n\n"
            "画一个眼眶含泪但倔强微笑的小女孩，避免描述伤害动作"
        )
        self.assertEqual(rewritten_prompt, result.final_prompt)
        self.assertEqual("把疼痛表达改成眼眶含泪和倔强微笑的中性视觉状态", result.prompt_change_summary)
        rewrite.assert_called_once()
        self.assertEqual(
            [
                call(
                    prompt="画一个倔强说不疼的小女孩",
                    references=[ImageReference(url="https://cdn.example.com/person.jpg")],
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                ),
                call(
                    prompt=rewritten_prompt,
                    references=[ImageReference(url="https://cdn.example.com/person.jpg")],
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                ),
            ],
            generate.call_args_list,
        )

    def test_non_policy_provider_error_does_not_switch_model(self) -> None:
        request = PreparedPanelImageRequest(
            panel_id="panel-1",
            panel_order=1,
            image_id="image-1",
            final_prompt="画一只猫",
            references=[],
            reference_count=0,
            character_reference_count=0,
            style_reference_count=0,
        )
        error = ImageProviderResponseError("图片 Provider 请求失败：HTTP 400 bad request")

        with patch("app.services.task_worker.generate_xg_image", side_effect=error) as generate, patch(
            "app.services.task_worker.rewrite_policy_blocked_image_prompt"
        ) as rewrite:
            result = generate_panel_image_request(
                task_id="task-1",
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
                request=request,
            )

        self.assertIs(result.error, error)
        self.assertTrue(is_policy_blocked_image_error(ImageProviderResponseError(str(error))) is False)
        generate.assert_called_once()
        rewrite.assert_not_called()


if __name__ == "__main__":
    unittest.main()
