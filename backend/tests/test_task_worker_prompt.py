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
        self.assertIn("对白必须出现在对应人物附近的对白气泡中", final_prompt)


if __name__ == "__main__":
    unittest.main()
