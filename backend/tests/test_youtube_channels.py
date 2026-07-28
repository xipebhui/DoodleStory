from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.youtube_channels import (
    sync_channel_analytics,
    sync_channels,
    update_channel_profile,
)
from app.core.database import Base
from app.models.entities import User, YoutubeChannel
from app.models.enums import UserRole
from app.schemas.youtube import YoutubeChannelProfileUpdate
from app.services.youtube_publisher import YoutubePublisherClient, YoutubePublisherError


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse(self.responses.pop(0))


class YoutubePublisherClientTests(unittest.TestCase):
    def settings(self):
        return SimpleNamespace(
            ytb_publish_url="https://publisher.example/",
            ytb_publish_api_key="secret",
            ytb_publish_timeout_seconds=30,
        )

    def test_video_list_always_filters_by_channel_and_follows_cursor(self) -> None:
        session = FakeSession(
            [
                {
                    "datas": [{"youtube_video_id": "v1", "channel_id": "UC1"}],
                    "next": {"youtube_video_id": "v1"},
                },
                {
                    "datas": [{"youtube_video_id": "v2", "channel_id": "UC1"}],
                    "next": None,
                },
            ]
        )
        rows = YoutubePublisherClient(self.settings(), session).channel_videos("UC1")

        self.assertEqual(["v1", "v2"], [row["youtube_video_id"] for row in rows])
        for _method, _url, kwargs in session.calls:
            self.assertEqual(
                {"one": {"channel_id": {"=": "UC1"}}},
                kwargs["json"]["where"],
            )
            self.assertEqual("secret", kwargs["headers"]["x-api-key"])
        self.assertEqual({"youtube_video_id": "v1"}, session.calls[1][2]["json"]["cursor"])

    def test_video_list_rejects_cross_channel_response(self) -> None:
        session = FakeSession(
            [{"datas": [{"youtube_video_id": "v1", "channel_id": "UC2"}], "next": None}]
        )
        with self.assertRaisesRegex(RuntimeError, "其他频道"):
            YoutubePublisherClient(self.settings(), session).channel_videos("UC1")


class YoutubeChannelApiTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def test_sync_is_idempotent_and_preserves_local_profile(self) -> None:
        with self.Session() as db:
            admin = User(email="admin@example.com", password_hash="hash", role=UserRole.admin)
            db.add(admin)
            db.commit()
            remote = [
                {
                    "channel_id": "UC1",
                    "title": "Remote title",
                    "handle": "remote",
                    "status": "normal",
                    "last_sync_at": "2026-07-28T10:00:00Z",
                    "last_sync_error": None,
                }
            ]
            with patch(
                "app.api.youtube_channels.YoutubePublisherClient.list_channels",
                return_value=remote,
            ):
                first = sync_channels(user=admin, db=db)
            channel = db.scalar(select(YoutubeChannel).where(YoutubeChannel.channel_id == "UC1"))
            self.assertIsNotNone(channel)
            update_channel_profile(
                channel.id,
                YoutubeChannelProfileUpdate(alias="英文主号", account_positioning="英文动画"),
                user=admin,
                db=db,
            )
            remote[0]["title"] = "Changed remote title"
            with patch(
                "app.api.youtube_channels.YoutubePublisherClient.list_channels",
                return_value=remote,
            ):
                second = sync_channels(user=admin, db=db)
            db.refresh(channel)

            self.assertEqual({"total": 1, "created": 1, "updated": 0}, first.data)
            self.assertEqual({"total": 1, "created": 0, "updated": 1}, second.data)
            self.assertEqual("Changed remote title", channel.title)
            self.assertEqual("英文主号", channel.alias)
            self.assertEqual("英文动画", channel.account_positioning)
            self.assertEqual(1, db.query(YoutubeChannel).count())

    def test_non_admin_cannot_sync(self) -> None:
        with self.Session() as db:
            user = User(email="user@example.com", password_hash="hash", role=UserRole.user)
            db.add(user)
            db.commit()
            with self.assertRaises(HTTPException) as caught:
                sync_channels(user=user, db=db)
            self.assertEqual(403, caught.exception.status_code)

    def test_analytics_error_preserves_last_successful_metrics(self) -> None:
        with self.Session() as db:
            admin = User(email="admin@example.com", password_hash="hash", role=UserRole.admin)
            channel = YoutubeChannel(
                channel_id="UC1",
                title="Channel",
                remote_status="normal",
                total_views=1234,
            )
            db.add_all([admin, channel])
            db.commit()

            with patch(
                "app.api.youtube_channels.YoutubePublisherClient.channel_analytics",
                side_effect=YoutubePublisherError("远程暂不可用"),
            ):
                with self.assertRaises(HTTPException) as caught:
                    sync_channel_analytics(channel.id, user=admin, db=db)

            db.refresh(channel)
            self.assertEqual(502, caught.exception.status_code)
            self.assertEqual(1234, channel.total_views)
            self.assertEqual("远程暂不可用", channel.last_sync_error)
