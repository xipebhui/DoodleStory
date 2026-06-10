import unittest

from app.api.tasks import (
    SUPERSEDED_IMAGE_ERROR_CODE,
    SUPERSEDED_IMAGE_ERROR_MESSAGE,
    current_succeeded_images_for_panels,
    download_meta_for_content_extraction,
    retire_superseded_running_images,
    task_has_all_panel_images,
)
from app.models.entities import ContentExtraction, GeneratedImage, GenerationTask, TaskPanel
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
    def test_douyin_download_meta_contains_source_title_description_and_tags(self) -> None:
        content = ContentExtraction(
            id="content",
            owner_user_id="user",
            raw_input="https://v.douyin.com/test/",
            source_url="https://v.douyin.com/test/",
            media_type="image",
            output_dir="/tmp/douyin/test",
            source_title="尴尬开场，温柔收场，我们刚好同校。",
            source_description="尴尬开场，温柔收场，我们刚好同校。#纯爱#恋爱#漫画",
            source_tags_json='["纯爱", "恋爱", "漫画"]',
        )

        self.assertEqual(
            {
                "title": "尴尬开场，温柔收场，我们刚好同校。",
                "description": "尴尬开场，温柔收场，我们刚好同校。#纯爱#恋爱#漫画",
                "tags": ["纯爱", "恋爱", "漫画"],
            },
            download_meta_for_content_extraction(content),
        )

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

    def test_retry_retires_superseded_running_images(self) -> None:
        task = make_task_with_panels(1)
        running = GeneratedImage(
            id="running-panel-1",
            task_id="task",
            panel_id="panel-1",
            status=GeneratedImageStatus.running,
            generation_number=1,
            is_current=True,
            image_model_name_snapshot="gpt-image-2",
        )
        task.generated_images = [running, make_current_success("panel-1", generation_number=2)]

        self.assertEqual(1, retire_superseded_running_images(task))

        self.assertEqual(GeneratedImageStatus.failed, running.status)
        self.assertFalse(running.is_current)
        self.assertEqual(SUPERSEDED_IMAGE_ERROR_CODE, running.error_code)
        self.assertEqual(SUPERSEDED_IMAGE_ERROR_MESSAGE, running.error_message)
        self.assertIsNotNone(running.finished_at)


if __name__ == "__main__":
    unittest.main()
