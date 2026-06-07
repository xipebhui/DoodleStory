import unittest

from app.models.enums import PanelType
from app.services.task_worker import build_adapted_story_final_prompt


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


if __name__ == "__main__":
    unittest.main()
