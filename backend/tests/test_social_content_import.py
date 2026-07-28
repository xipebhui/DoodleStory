import unittest
from unittest.mock import Mock, patch

from app.services.social_content_import import (
    SocialContentImportError,
    import_social_content,
)


class SocialContentImportTests(unittest.TestCase):
    @patch("app.services.social_content_import.requests.post")
    def test_import_social_content_maps_unified_response(self, post: Mock) -> None:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "platform": "wechat",
            "url": "https://mp.weixin.qq.com/s/source",
            "resolved_url": "https://mp.weixin.qq.com/s/resolved",
            "output_dir": "/tmp/wechat/article",
            "content_type": "article",
            "content_id": "source",
            "title": "测试文章",
            "description": "摘要",
            "tags": ["内容"],
            "author_name": "测试公众号",
            "publish_time": "2026-07-28",
            "publish_timestamp": 1785168000,
            "media_files": ["/tmp/wechat/article/images/1.jpg"],
            "metadata_files": ["/tmp/wechat/article/content.md"],
            "comment_files": [],
            "manifest_path": "/tmp/wechat/article/wechat.json",
            "metrics": {"image_count": 1},
        }

        result = import_social_content("https://mp.weixin.qq.com/s/source")

        self.assertEqual("wechat", result.platform)
        self.assertEqual("测试文章", result.title)
        self.assertEqual("content.md", result.metadata_files[0].name)
        self.assertEqual({"image_count": 1}, result.metrics)
        post.assert_called_once()
        self.assertEqual(
            {"url": "https://mp.weixin.qq.com/s/source", "include_comments": False},
            post.call_args.kwargs["json"],
        )

    @patch("app.services.social_content_import.requests.post")
    def test_import_social_content_rejects_invalid_metrics(self, post: Mock) -> None:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "platform": "wechat",
            "url": "https://mp.weixin.qq.com/s/source",
            "resolved_url": "https://mp.weixin.qq.com/s/source",
            "output_dir": "/tmp/wechat/article",
            "metadata_files": [],
            "metrics": {"nested": {"unsupported": True}},
        }

        with self.assertRaisesRegex(SocialContentImportError, "metrics"):
            import_social_content("https://mp.weixin.qq.com/s/source")
