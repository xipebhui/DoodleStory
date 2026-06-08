import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.api.content_extractions import (
    CONTENT_EXTRACTION_INTERRUPTED_MESSAGE,
    DownloadedAssetCandidate,
    mark_content_extraction_interrupted,
    save_downloaded_assets_parallel,
)
from app.models.enums import ContentExtractionMediaKind
from app.services.media_text_extraction import (
    ImageExtractionReference,
    LLMResponseError,
    extract_ordered_gallery_comic_content,
)


class ContentExtractionMediaFlowTest(unittest.TestCase):
    def test_ordered_gallery_uses_public_image_urls(self) -> None:
        captured: dict[str, object] = {}

        def fake_chat_multimodal(*, model: str, content: list[dict[str, object]], prompt_name: str) -> str:
            captured["model"] = model
            captured["content"] = content
            captured["prompt_name"] = prompt_name
            return "第1页：测试"

        settings = SimpleNamespace(siliconflow_vision_model="vision-model")
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
        content = SimpleNamespace(processing_status="processing", processing_error_message=None)

        mark_content_extraction_interrupted(content)

        self.assertEqual("failed", content.processing_status)
        self.assertEqual(CONTENT_EXTRACTION_INTERRUPTED_MESSAGE, content.processing_error_message)


if __name__ == "__main__":
    unittest.main()
