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


if __name__ == "__main__":
    unittest.main()
