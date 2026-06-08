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
from app.services.image_generation import GeneratedImageFile, ImageReference, ImageProviderResponseError
from app.services.task_worker import (
    PreparedPanelImageRequest,
    build_adapted_story_final_prompt,
    build_generation_reference_pack,
    build_panel_final_prompt,
    generate_panel_image_request,
    is_policy_blocked_image_error,
)


class TaskWorkerPromptTest(unittest.TestCase):
    def test_final_prompt_includes_dialogue_text(self) -> None:
        final_prompt = build_adapted_story_final_prompt(
            aspect_ratio="3:4",
            visual_prompt="主画面+右下角分镜布局，父亲伸手阻止，孩子哭着跑开。",
            story_beat="男主焦急地阻止儿子，孩子被吓哭。",
            panel_type=PanelType.scene,
            image_text={
                "title": None,
                "narration": "我急得朝他吼了一下\n他吓的哭了出来\n去喊我老婆",
                "dialogue": "你个熊孩子\n别拿这个乱玩\n拿过来\n呜哇",
                "inner_os": None,
                "emphasis": None,
            },
            reference_notes=["男主角/丈夫参考（参考图1）", "儿子参考（参考图2）"],
            text_layout="主画面+右下角分镜",
        )

        self.assertIn("以旁白框或字幕框呈现：「我急得朝他吼了一下\n他吓的哭了出来\n去喊我老婆」", final_prompt)
        self.assertIn("以对白气泡呈现：「你个熊孩子\n别拿这个乱玩\n拿过来\n呜哇」", final_prompt)
        self.assertIn("对白出现在对应人物附近的对白气泡中", final_prompt)
        self.assertNotIn("旁白：", final_prompt)
        self.assertNotIn("对白：", final_prompt)
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
        self.assertLess(final_prompt.index("风格提示词"), final_prompt.index("画面比例：3:4"))

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
        self.assertIn("画面必须采用上下两格。", final_prompt)
        self.assertNotIn("分格/多栏布局：", final_prompt)
        self.assertNotIn("旁白：", final_prompt)

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

        self.assertIn("以旁白框或字幕框呈现：「嘴里还一直喊：“别被追上！你们太小了！”」", final_prompt)
        self.assertNotIn("分格/多栏布局：", final_prompt)
        self.assertNotIn("单页漫画构图\n", final_prompt)
        self.assertNotIn("旁白：", final_prompt)

    def test_panel_final_prompt_omits_style_prompt_in_image_reference_mode(self) -> None:
        task = GenerationTask(
            owner_user_id="user",
            display_title="任务",
            original_text="原文",
            story_input_mode=StoryInputMode.original,
            image_count_mode=ImageCountMode.auto,
            style_id="style",
            style_name_snapshot="参考图风格",
            style_prompt_snapshot="这段风格提示词不应直接进入最终生图 prompt",
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
        self.assertNotIn("风格提示词（必须直接用于本张图", final_prompt)
        self.assertNotIn("这段风格提示词不应直接进入最终生图 prompt", final_prompt)

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
        self.assertEqual(["张三参考（参考图1）", "风格参考（参考图2）"], pack.notes)
        self.assertEqual(1, pack.character_reference_count)
        self.assertEqual(1, pack.style_reference_count)

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
        self.assertEqual("画一个眼眶含泪但倔强微笑的小女孩，避免描述伤害动作", result.final_prompt)
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
                    prompt="画一个眼眶含泪但倔强微笑的小女孩，避免描述伤害动作",
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
