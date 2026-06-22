import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.api.content_extractions import (
    CONTENT_EXTRACTION_INTERRUPTED_MESSAGE,
    TASK_CREATE_FAILED_STATUS,
    TASK_CREATE_PENDING_STATUS,
    TASK_CREATE_SUCCEEDED_STATUS,
    DownloadedAssetCandidate,
    create_generation_task_from_content_extraction,
    mark_content_extraction_interrupted,
    save_downloaded_assets_parallel,
)
from app.models.enums import ContentExtractionMediaKind, ImageCountMode, StoryInputMode
from app.services.douyin_import_service import download_douyin_content
from app.services.media_text_extraction import (
    ImageExtractionReference,
    LLMResponseError,
    extract_ordered_gallery_comic_content,
)


class FakeDouyinResponse:
    def __init__(self, status_code: int, payload: dict[str, object]):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, object]:
        return self._payload


class ContentExtractionMediaFlowTest(unittest.TestCase):
    def test_douyin_download_keeps_source_meta_fields(self) -> None:
        settings = SimpleNamespace(douyin_import_service_base_url="http://127.0.0.1:8010")
        response = FakeDouyinResponse(
            200,
            {
                "url": "https://v.douyin.com/test/",
                "output_dir": "/tmp/douyin/test",
                "media_type": "image",
                "aweme_id": "123",
                "media_files": ["/tmp/douyin/test/1.jpg"],
                "metadata_files": [],
                "manifest_path": "/tmp/douyin/test/manifest.json",
                "title": "尴尬开场，温柔收场，我们刚好同校。",
                "description": "尴尬开场，温柔收场，我们刚好同校。#纯爱#恋爱#漫画",
                "tags": ["纯爱", "恋爱", "漫画"],
                "author_name": "杰哥是纯爱",
                "publish_timestamp": 1775815824,
            },
        )

        with patch("app.services.douyin_import_service.get_settings", return_value=settings), patch(
            "app.services.douyin_import_service.requests.post",
            return_value=response,
        ):
            result = download_douyin_content("https://v.douyin.com/test/")

        self.assertEqual("尴尬开场，温柔收场，我们刚好同校。", result.title)
        self.assertEqual("尴尬开场，温柔收场，我们刚好同校。#纯爱#恋爱#漫画", result.description)
        self.assertEqual(["纯爱", "恋爱", "漫画"], result.tags)

    def test_ordered_gallery_uses_public_image_urls(self) -> None:
        captured: dict[str, object] = {}

        def fake_chat_multimodal(*, model: str, content: list[dict[str, object]], prompt_name: str) -> str:
            captured["model"] = model
            captured["content"] = content
            captured["prompt_name"] = prompt_name
            return "第1页：测试"

        settings = SimpleNamespace(lio_vision_model="vision-model")
        images = [
            ImageExtractionReference(url="https://cdn.example.com/1.jpg", source_path="/source/1.jpg"),
            ImageExtractionReference(url="https://cdn.example.com/2.jpg", source_path="/source/2.jpg"),
        ]

        with patch("app.services.media_text_extraction.get_settings", return_value=settings), patch(
            "app.services.media_text_extraction._chat_multimodal",
            side_effect=fake_chat_multimodal,
        ):
            result = extract_ordered_gallery_comic_content(images)

        self.assertEqual("第1页：测试", result.text)
        self.assertEqual("vision-model", result.model)
        content = captured["content"]
        image_parts = [part["image_url"] for part in content if part.get("type") == "image_url"]
        self.assertEqual("https://cdn.example.com/1.jpg", image_parts[0]["url"])
        self.assertEqual("https://cdn.example.com/2.jpg", image_parts[1]["url"])
        self.assertFalse(any(str(part["url"]).startswith("data:image") for part in image_parts))

    def test_ordered_gallery_rejects_non_public_image_urls(self) -> None:
        with self.assertRaisesRegex(LLMResponseError, "公网 HTTP\\(S\\) URL"):
            extract_ordered_gallery_comic_content(
                [ImageExtractionReference(url="/api/v1/assets/asset1/content", source_path="/source/1.jpg")]
            )

    def test_parallel_asset_upload_preserves_display_order(self) -> None:
        candidates = [
            DownloadedAssetCandidate(1, Path("/source/1.jpg"), ContentExtractionMediaKind.image),
            DownloadedAssetCandidate(2, Path("/source/2.jpg"), ContentExtractionMediaKind.image),
            DownloadedAssetCandidate(3, Path("/source/meta.json"), ContentExtractionMediaKind.metadata),
        ]

        def fake_save_path_as_asset(path: Path, media_kind: ContentExtractionMediaKind):
            if path.name == "1.jpg":
                time.sleep(0.02)
            return SimpleNamespace(
                storage_backend=SimpleNamespace(value="qiniu"),
                storage_key=f"stored/{path.name}",
                byte_size=len(path.name),
            )

        with patch("app.api.content_extractions.save_path_as_asset", side_effect=fake_save_path_as_asset):
            saved = save_downloaded_assets_parallel(candidates)

        self.assertEqual([1, 2, 3], [item.candidate.display_order for item in saved])
        self.assertEqual(
            ["stored/1.jpg", "stored/2.jpg", "stored/meta.json"],
            [item.asset.storage_key for item in saved],
        )

    def test_interrupted_processing_content_is_marked_failed(self) -> None:
        content = SimpleNamespace(
            processing_status="processing",
            processing_error_message=None,
            task_create_status=TASK_CREATE_PENDING_STATUS,
            task_create_error_message=None,
        )

        mark_content_extraction_interrupted(content)

        self.assertEqual("failed", content.processing_status)
        self.assertEqual(CONTENT_EXTRACTION_INTERRUPTED_MESSAGE, content.processing_error_message)
        self.assertEqual(TASK_CREATE_FAILED_STATUS, content.task_create_status)
        self.assertEqual(CONTENT_EXTRACTION_INTERRUPTED_MESSAGE, content.task_create_error_message)

    def test_replicate_content_creates_extracted_storyboard_task(self) -> None:
        content = SimpleNamespace(
            extracted_text="第1页：\n画面：女孩拿着通知书\n旁白：通知来了",
            linked_task_id=None,
            task_create_status=TASK_CREATE_PENDING_STATUS,
            task_create_error_message=None,
        )
        payload = SimpleNamespace(
            image_count_mode=ImageCountMode.auto,
            requested_image_count=None,
            style_id="style-1",
            use_character_references=True,
        )
        user = SimpleNamespace(id="user-1")
        db = object()

        def fake_create_generation_task_record(*, db, payload, user):
            self.assertEqual("第1页：\n画面：女孩拿着通知书\n旁白：通知来了", payload.original_text)
            self.assertEqual(StoryInputMode.extracted_storyboard, payload.story_input_mode)
            self.assertEqual(ImageCountMode.auto, payload.image_count_mode)
            self.assertIsNone(payload.requested_image_count)
            self.assertEqual("style-1", payload.style_id)
            self.assertTrue(payload.use_character_references)
            return SimpleNamespace(id="task-1")

        with patch(
            "app.api.content_extractions.create_generation_task_record",
            side_effect=fake_create_generation_task_record,
        ):
            task_id = create_generation_task_from_content_extraction(content, payload, user, db)

        self.assertEqual("task-1", task_id)
        self.assertEqual("task-1", content.linked_task_id)
        self.assertEqual(TASK_CREATE_SUCCEEDED_STATUS, content.task_create_status)
        self.assertIsNone(content.task_create_error_message)


if __name__ == "__main__":
    unittest.main()
