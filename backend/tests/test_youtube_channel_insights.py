from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from app.services.youtube_channel_insights import (
    YoutubeChannelInsightsError,
    fetch_youtube_channel_insights,
)


def response_payload(root: Path) -> dict[str, object]:
    avatar = root / "channel-avatar.jpg"
    cover = root / "videos" / "01-video.jpg"
    cover.parent.mkdir(parents=True)
    avatar.write_bytes(b"avatar")
    cover.write_bytes(b"cover")
    return {
        "observed_at": "2026-07-30T00:00:00+00:00",
        "output_dir": str(root),
        "request": {
            "channel": "@HistoryEagle-u9d",
            "video_limit": 1,
            "comments_per_video": 2,
            "comment_order": "relevance",
        },
        "channel": {
            "id": "UCe39qjiOYSfAhkir-WLafGA",
            "url": "https://www.youtube.com/@historyeagle-u9d",
            "title": "History Eagle",
            "handle": "@historyeagle-u9d",
            "description": "Channel description",
            "country": "US",
            "created_at": "2026-05-08T13:50:48Z",
            "subscriber_count": 339,
            "hidden_subscriber_count": False,
            "view_count": 81473,
            "video_count": 3,
            "privacy_status": "public",
            "made_for_kids": False,
            "keywords": "history documentary",
            "topic_categories": [
                "https://en.wikipedia.org/wiki/Knowledge"
            ],
            "avatar": {
                "url": "https://img.example/avatar.jpg",
                "width": 800,
                "height": 800,
                "file_path": str(avatar),
                "content_type": "image/jpeg",
                "byte_size": 6,
            },
        },
        "videos": [
            {
                "id": "2XtwNq0G7Tk",
                "url": "https://www.youtube.com/watch?v=2XtwNq0G7Tk",
                "title": "The Most POWERFUL Military Units",
                "description": "Full video description",
                "tags": ["history", "military"],
                "published_at": "2026-07-19T20:00:08Z",
                "duration": "PT18M55S",
                "definition": "hd",
                "caption_available": False,
                "privacy_status": "public",
                "view_count": 95506,
                "like_count": 1066,
                "comment_count": 118,
                "thumbnail": {
                    "url": "https://img.example/cover.jpg",
                    "width": 1280,
                    "height": 720,
                    "file_path": str(cover),
                    "content_type": "image/jpeg",
                    "byte_size": 5,
                },
                "comments": [
                    {
                        "id": "comment-1",
                        "author": "@viewer",
                        "text": "Great video",
                        "like_count": 8,
                        "reply_count": 2,
                        "published_at": "2026-07-26T18:46:44Z",
                        "updated_at": "2026-07-26T18:46:44Z",
                    }
                ],
            }
        ],
    }


class YoutubeChannelInsightsClientTests(unittest.TestCase):
    @patch("app.services.youtube_channel_insights.requests.post")
    def test_maps_response_and_verifies_downloaded_images(
        self,
        post: Mock,
    ) -> None:
        with TemporaryDirectory() as directory:
            payload = response_payload(Path(directory))
            post.return_value.status_code = 200
            post.return_value.json.return_value = payload

            result = fetch_youtube_channel_insights(
                "@HistoryEagle-u9d",
                video_limit=1,
                comments_per_video=2,
                comment_order="relevance",
            )

        self.assertEqual("History Eagle", result.channel.title)
        self.assertEqual(
            "Full video description",
            result.videos[0].description,
        )
        self.assertEqual(95506, result.videos[0].view_count)
        self.assertEqual("Great video", result.videos[0].comments[0].text)
        self.assertEqual(
            {
                "channel": "@HistoryEagle-u9d",
                "video_limit": 1,
                "comments_per_video": 2,
                "comment_order": "relevance",
            },
            post.call_args.kwargs["json"],
        )

    @patch("app.services.youtube_channel_insights.requests.post")
    def test_rejects_missing_downloaded_cover(self, post: Mock) -> None:
        with TemporaryDirectory() as directory:
            payload = response_payload(Path(directory))
            Path(payload["videos"][0]["thumbnail"]["file_path"]).unlink()
            post.return_value.status_code = 200
            post.return_value.json.return_value = payload

            with self.assertRaisesRegex(
                YoutubeChannelInsightsError,
                "图片文件不存在",
            ):
                fetch_youtube_channel_insights("@HistoryEagle-u9d")
