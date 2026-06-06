import unittest

from app.api.tasks import current_succeeded_images_for_panels, task_has_all_panel_images
from app.models.entities import GeneratedImage, GenerationTask, TaskPanel
from app.models.enums import GeneratedImageStatus, TaskStatus


def make_task_with_panels(panel_count: int) -> GenerationTask:
    task = GenerationTask(id="task", status=TaskStatus.succeeded)
    task.panels = [
        TaskPanel(id=f"panel-{index}", panel_order=index, original_text_segment=f"第 {index} 格")
        for index in range(1, panel_count + 1)
    ]
    task.generated_images = []
    return task


def make_current_success(panel_id: str, generation_number: int = 1) -> GeneratedImage:
    return GeneratedImage(
        id=f"image-{panel_id}-{generation_number}",
        task_id="task",
        panel_id=panel_id,
        status=GeneratedImageStatus.succeeded,
        generation_number=generation_number,
        is_current=True,
        asset_id=f"asset-{panel_id}-{generation_number}",
        image_model_name_snapshot="gpt-image-2",
    )


class TaskDownloadStateTest(unittest.TestCase):
    def test_partial_current_images_are_not_complete(self) -> None:
        task = make_task_with_panels(2)
        task.generated_images = [make_current_success("panel-1")]

        self.assertFalse(task_has_all_panel_images(task))
        self.assertEqual(1, len(current_succeeded_images_for_panels(task)))

    def test_all_panels_need_current_success_images(self) -> None:
        task = make_task_with_panels(2)
        task.generated_images = [
            make_current_success("panel-1"),
            GeneratedImage(
                id="old-panel-2",
                task_id="task",
                panel_id="panel-2",
                status=GeneratedImageStatus.succeeded,
                generation_number=1,
                is_current=False,
                asset_id="old-asset-panel-2",
                image_model_name_snapshot="gpt-image-2",
            ),
        ]

        self.assertFalse(task_has_all_panel_images(task))

        task.generated_images.append(make_current_success("panel-2", generation_number=2))

        self.assertTrue(task_has_all_panel_images(task))
        self.assertEqual(["panel-1", "panel-2"], [image.panel_id for image in current_succeeded_images_for_panels(task)])


if __name__ == "__main__":
    unittest.main()
