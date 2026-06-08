import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.style import FileAssetRead
from app.services.storage import qiniu_asset_url


class QiniuAssetUrlTest(unittest.TestCase):
    def test_qiniu_read_urls_do_not_append_thumbnail_query(self) -> None:
        now = datetime(2026, 6, 8, 12, 0, 0)
        asset = FileAssetRead(
            id="asset1",
            purpose="generated_image",
            storage_backend="qiniu",
            original_filename="panel.jpg",
            content_type="image/jpeg",
            byte_size=1024,
            public_url="http://cdn.example.com/generated_image/panel.jpg",
            width=896,
            height=1200,
            created_at=now,
            updated_at=now,
        )

        self.assertEqual("http://cdn.example.com/generated_image/panel.jpg", asset.content_url)
        self.assertEqual("http://cdn.example.com/generated_image/panel.jpg", asset.thumbnail_url)

    def test_qiniu_asset_url_thumbnail_uses_original_object_url(self) -> None:
        settings = SimpleNamespace(
            qiniu_bucket_domain="",
            qny_public_base_url="http://cdn.example.com",
            qny_domain="",
            qny_use_https=False,
            qiniu_access_key="",
            qny_access_key="",
            qiniu_secret_key="",
            qny_secret_key="",
            qiniu_bucket="",
            qny_bucket="",
        )

        with patch("app.services.storage.get_settings", return_value=settings):
            self.assertEqual(
                "http://cdn.example.com/generated_image/panel.jpg",
                qiniu_asset_url("generated_image/panel.jpg", "thumbnail"),
            )


if __name__ == "__main__":
    unittest.main()
