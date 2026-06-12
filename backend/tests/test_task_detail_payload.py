import unittest

from app.schemas.task import GeneratedImageDebugRead, GeneratedImageRead, TaskPanelDebugRead, TaskPanelRead


class TaskDetailPayloadTest(unittest.TestCase):
    def test_task_detail_panel_schema_excludes_large_text_fields(self) -> None:
        fields = set(TaskPanelRead.model_fields)

        self.assertNotIn("original_text_segment", fields)
        self.assertNotIn("narration_text", fields)
        self.assertNotIn("dialogue_text", fields)
        self.assertNotIn("image_text_json", fields)
        self.assertNotIn("text_layout", fields)
        self.assertNotIn("generated_prompt", fields)

    def test_task_detail_image_schema_excludes_prompt_fields(self) -> None:
        fields = set(GeneratedImageRead.model_fields)

        self.assertNotIn("previous_prompt", fields)
        self.assertNotIn("image_prompt", fields)
        self.assertNotIn("final_prompt", fields)
        self.assertNotIn("image_text_json", fields)
        self.assertNotIn("text_layout", fields)

    def test_debug_schemas_include_click_to_load_fields(self) -> None:
        panel_fields = set(TaskPanelDebugRead.model_fields)
        image_fields = set(GeneratedImageDebugRead.model_fields)

        self.assertIn("original_text_segment", panel_fields)
        self.assertIn("generated_prompt", panel_fields)
        self.assertIn("images", panel_fields)
        self.assertIn("image_text_json", image_fields)
        self.assertIn("text_layout", image_fields)
        self.assertIn("previous_prompt", image_fields)
        self.assertIn("image_prompt", image_fields)
        self.assertIn("final_prompt", image_fields)


if __name__ == "__main__":
    unittest.main()
