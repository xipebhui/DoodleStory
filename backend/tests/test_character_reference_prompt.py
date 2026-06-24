import unittest

from app.services.character_references import build_character_reference_prompt


class CharacterReferencePromptTest(unittest.TestCase):
    def test_character_reference_prompt_explicitly_includes_style_prompt_block(self) -> None:
        prompt = build_character_reference_prompt(
            style_prompt="低饱和手绘漫画风，细线条，浅色水彩，人物圆脸小五官。",
            aspect_ratio="3:4",
            character_name="丈夫 / 老公",
            age_stage="成年",
            visual_prompt="成年男性，短发，蓝色短袖T恤，身材高大可靠。",
        )

        self.assertIn("风格提示词（必须直接用于这张人物参考图", prompt)
        self.assertIn("低饱和手绘漫画风，细线条，浅色水彩，人物圆脸小五官。", prompt)
        self.assertLess(prompt.index("风格提示词"), prompt.index("画面比例是 3:4"))
        self.assertIn("人物外观设定：成年男性，短发，蓝色短袖T恤，身材高大可靠。", prompt)
        self.assertIn("上半部分：一张正面主图", prompt)
        self.assertIn("下半部分：两个侧视图并排展示", prompt)
        self.assertIn("左侧视图和右侧视图", prompt)
        self.assertIn("三张视图必须是同一个人物", prompt)

    def test_character_reference_prompt_uses_style_reference_notes_without_style_prompt(self) -> None:
        prompt = build_character_reference_prompt(
            style_prompt="这段风格提示词不应进入图片参考模式的人物参考图 prompt",
            aspect_ratio="3:4",
            character_name="三叔",
            age_stage="中年",
            visual_prompt="中年男性，黑色短发，神情严肃，穿深色夹克。",
            style_reference_notes=["风格参考（参考图1）"],
        )

        self.assertIn("风格参考图（必须直接用于这张人物参考图", prompt)
        self.assertIn("风格参考（参考图1）", prompt)
        self.assertIn("这些图片只作为风格参考，不代表人物身份或剧情内容", prompt)
        self.assertNotIn("这段风格提示词不应进入图片参考模式的人物参考图 prompt", prompt)
        self.assertIn("人物是 三叔，年龄阶段是 中年", prompt)


if __name__ == "__main__":
    unittest.main()
