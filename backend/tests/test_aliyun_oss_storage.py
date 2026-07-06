import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.models.enums import StorageBackend
from app.schemas.style import FileAssetRead
from app.services.storage import aliyun_oss_asset_url, store_content


class AliyunOssStorageTest(unittest.TestCase):
    def test_aliyun_oss_asset_url_uses_default_public_bucket_domain(self) -> None:
        settings = SimpleNamespace(
            aliyun_oss_access_key_id="access-key",
            aliyun_oss_access_key_secret="secret-key",
            aliyun_oss_bucket="doodlestory",
            aliyun_oss_endpoint="https://oss-cn-beijing.aliyuncs.com",
            aliyun_oss_public_base_url="",
        )

        with patch("app.services.storage.get_settings", return_value=settings):
            self.assertEqual(
                "https://doodlestory.oss-cn-beijing.aliyuncs.com/douyin_media/panel%201.jpg",
                aliyun_oss_asset_url("douyin_media/panel 1.jpg", "original"),
            )

    def test_store_content_uploads_to_aliyun_oss_and_keeps_local_mirror(self) -> None:
        settings = SimpleNamespace(
            storage_backend="aliyun_oss",
            doodlestory_storage_root="./storage",
            storage_root=Path("/tmp/doodlestory-test-storage"),
        )

        with patch("app.services.storage.get_settings", return_value=settings), patch(
            "app.services.storage.write_local_file",
        ) as write_local_file, patch(
            "app.services.storage.resolve_storage_key",
            return_value=Path("/tmp/doodlestory-test-storage/douyin_media/test.jpg"),
        ), patch(
            "app.services.storage.upload_aliyun_oss_file",
            return_value="https://doodlestory.oss-cn-beijing.aliyuncs.com/douyin_media/test.jpg",
        ) as upload_aliyun_oss_file:
            stored = store_content("douyin_media", b"image-bytes", ".jpg")

        self.assertEqual(StorageBackend.aliyun_oss, stored.storage_backend)
        self.assertEqual("https://doodlestory.oss-cn-beijing.aliyuncs.com/douyin_media/test.jpg", stored.public_url)
        write_local_file.assert_called_once()
        upload_aliyun_oss_file.assert_called_once()

    def test_file_asset_read_uses_public_url_for_aliyun_oss(self) -> None:
        now = datetime(2026, 7, 6, 12, 0, 0)
        asset = FileAssetRead(
            id="asset1",
            purpose="douyin_media",
            storage_backend="aliyun_oss",
            original_filename="panel.jpg",
            content_type="image/jpeg",
            byte_size=1024,
            public_url="https://doodlestory.oss-cn-beijing.aliyuncs.com/douyin_media/panel.jpg",
            width=896,
            height=1200,
            created_at=now,
            updated_at=now,
        )

        self.assertEqual(asset.public_url, asset.content_url)
        self.assertEqual(asset.public_url, asset.thumbnail_url)


if __name__ == "__main__":
    unittest.main()
