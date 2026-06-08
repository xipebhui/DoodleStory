import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from app.models.enums import PanelType, StorageBackend
from app.services.image_generation import GeneratedImageFile, ImageReference, ImageProviderResponseError
from app.services.task_worker import (
    PreparedPanelImageRequest,
    build_adapted_story_final_prompt,
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

        self.assertIn("旁白：「我急得朝他吼了一下\n他吓的哭了出来\n去喊我老婆」", final_prompt)
        self.assertIn("对白：「你个熊孩子\n别拿这个乱玩\n拿过来\n呜哇」", final_prompt)
        self.assertIn("对白出现在对应人物附近的对白气泡中", final_prompt)
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
