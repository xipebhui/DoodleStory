from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.youtube_channels import (
    list_channel_videos,
    list_channels,
    sync_channel_analytics,
    sync_channels,
    update_channel_profile,
)
from app.api.pagination import Pagination
from app.core.database import Base
from app.models.entities import (
    PublishableVideo,
    User,
    YoutubeChannel,
    YoutubePublishTask,
    YoutubeUploadedVideo,
)
from app.models.enums import UserRole
from app.schemas.youtube import YoutubeChannelProfileUpdate
from app.services.youtube_publisher import (
    YoutubePublisherClient,
    YoutubePublisherError,
    YoutubePublisherOutcomeUnknown,
)
from app.services.youtube_publishing import (
    YoutubePublishCommand,
    YoutubePublishingConflict,
    YoutubePublishingForbidden,
    create_youtube_publish_task,
    refresh_youtube_publish_task,
)


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

    def test_channel_list_uses_bounded_server_pagination(self) -> None:
        with self.Session() as db:
            admin = User(email="admin@example.com", password_hash="hash", role=UserRole.admin)
            db.add(admin)
            db.add_all(
                [
                    YoutubeChannel(
                        channel_id=f"UC{index}",
                        title=f"Channel {index}",
                        remote_status="normal" if index != 1 else "manual",
                    )
                    for index in range(4)
                ]
            )
            db.commit()

            first = list_channels(
                q=None,
                remote_status="normal",
                pagination=Pagination(limit=2, offset=0),
                user=admin,
                db=db,
            )
            second = list_channels(
                q=None,
                remote_status="normal",
                pagination=Pagination(limit=2, offset=2),
                user=admin,
                db=db,
            )

            self.assertEqual(3, first.page.total)
            self.assertEqual(2, len(first.items))
            self.assertTrue(first.page.has_more)
            self.assertEqual("2", first.page.next_cursor)
            self.assertEqual(1, len(second.items))
            self.assertFalse(second.page.has_more)

    def test_uploaded_video_list_is_paginated_and_channel_scoped(self) -> None:
        with self.Session() as db:
            admin = User(email="admin@example.com", password_hash="hash", role=UserRole.admin)
            other_user = User(email="user@example.com", password_hash="hash", role=UserRole.user)
            channel = YoutubeChannel(channel_id="UC1", title="Channel", remote_status="normal")
            other_channel = YoutubeChannel(channel_id="UC2", title="Other", remote_status="normal")
            db.add_all([admin, other_user, channel, other_channel])
            db.flush()
            db.add_all(
                [
                    YoutubeUploadedVideo(
                        channel_id=channel.id,
                        youtube_video_id=f"video-{index}",
                        title=f"Video {index}",
                        uploaded_at=datetime(2026, 7, 20 + index),
                    )
                    for index in range(1, 4)
                ]
                + [
                    YoutubeUploadedVideo(
                        channel_id=other_channel.id,
                        youtube_video_id="other-video",
                        title="Other video",
                        uploaded_at=datetime(2026, 7, 28),
                    )
                ]
            )
            db.commit()

            first = list_channel_videos(
                channel.id,
                pagination=Pagination(limit=2, offset=0),
                user=admin,
                db=db,
            )
            second = list_channel_videos(
                channel.id,
                pagination=Pagination(limit=2, offset=2),
                user=admin,
                db=db,
            )

            self.assertEqual(["video-3", "video-2"], [item.youtube_video_id for item in first.items])
            self.assertEqual(3, first.page.total)
            self.assertTrue(first.page.has_more)
            self.assertEqual(["video-1"], [item.youtube_video_id for item in second.items])
            self.assertFalse(second.page.has_more)
            with self.assertRaises(HTTPException) as caught:
                list_channel_videos(
                    channel.id,
                    pagination=Pagination(limit=2, offset=0),
                    user=other_user,
                    db=db,
                )
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


class FakePublishClient:
    def __init__(
        self,
        *,
        created: dict | None = None,
        refreshed: dict | None = None,
        create_error: Exception | None = None,
    ) -> None:
        self.created = created or {"id": "remote-1", "task_status": "pending"}
        self.refreshed = refreshed or self.created
        self.create_error = create_error
        self.create_payloads: list[dict] = []

    def create_upload_task(self, payload: dict) -> dict:
        self.create_payloads.append(payload)
        if self.create_error is not None:
            raise self.create_error
        return self.created

    def upload_task(self, remote_task_id: str) -> dict:
        del remote_task_id
        return self.refreshed


class YoutubePublishingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def seed(self, db, *, review_status: str = "approved"):
        user = User(email="admin@example.com", password_hash="hash", role=UserRole.admin)
        channel = YoutubeChannel(
            channel_id="UC1",
            title="Channel",
            remote_status="normal",
        )
        db.add_all([user, channel])
        db.flush()
        video = PublishableVideo(
            owner_user_id=user.id,
            source_native_agent_video_id="native-video-1",
            video_url="https://cdn.example/video.mp4",
            thumbnail_url="https://cdn.example/cover.jpg",
            title="Title",
            description="Description",
            tags_json='["tag1"]',
            contains_synthetic_media=True,
            review_status=review_status,
        )
        db.add(video)
        db.commit()
        return user, channel, video

    def command(self, user, channel, video, **overrides):
        values = {
            "owner_user_id": user.id,
            "channel_id": channel.id,
            "publishable_video_id": video.id,
            "visibility": "public",
            "planned_publish_at": datetime(2026, 7, 29, 3, 0, 0),
            "notify_subscribers": True,
            "confirmed": True,
            "idempotency_key": "publish-test-key",
        }
        values.update(overrides)
        return YoutubePublishCommand(**values)

    def test_create_maps_request_and_idempotently_reuses_task(self) -> None:
        with self.Session() as db:
            user, channel, video = self.seed(db)
            client = FakePublishClient()
            task = create_youtube_publish_task(
                db,
                self.command(user, channel, video),
                client=client,
            )
            repeated = create_youtube_publish_task(
                db,
                self.command(user, channel, video),
                client=client,
            )

            self.assertEqual(task.id, repeated.id)
            self.assertEqual(1, len(client.create_payloads))
            payload = client.create_payloads[0]
            self.assertEqual("UC1", payload["channel_id"])
            self.assertEqual(
                "Title",
                payload["upload_args"]["body"]["snippet"]["title"],
            )
            self.assertEqual(
                "public",
                payload["upload_args"]["body"]["status"]["privacyStatus"],
            )
            self.assertEqual("native-video-1", task.source_native_agent_video_id)

    def test_unconfirmed_or_unapproved_video_never_calls_remote(self) -> None:
        with self.Session() as db:
            user, channel, video = self.seed(db, review_status="draft")
            client = FakePublishClient()
            with self.assertRaises(YoutubePublishingForbidden):
                create_youtube_publish_task(
                    db,
                    self.command(user, channel, video),
                    client=client,
                )
            video.review_status = "approved"
            db.commit()
            with self.assertRaises(YoutubePublishingForbidden):
                create_youtube_publish_task(
                    db,
                    self.command(user, channel, video, confirmed=False),
                    client=client,
                )
            self.assertEqual([], client.create_payloads)

    def test_unknown_create_result_is_locked_against_duplicate(self) -> None:
        with self.Session() as db:
            user, channel, video = self.seed(db)
            client = FakePublishClient(
                create_error=YoutubePublisherOutcomeUnknown("timeout")
            )
            task = create_youtube_publish_task(
                db,
                self.command(user, channel, video),
                client=client,
            )
            self.assertEqual("outcome_unknown", task.status)
            with self.assertRaises(YoutubePublishingConflict):
                create_youtube_publish_task(
                    db,
                    self.command(
                        user,
                        channel,
                        video,
                        idempotency_key="different-key",
                    ),
                    client=FakePublishClient(),
                )

    def test_refresh_completed_creates_permanent_three_id_link(self) -> None:
        with self.Session() as db:
            user, channel, video = self.seed(db)
            task = create_youtube_publish_task(
                db,
                self.command(user, channel, video),
                client=FakePublishClient(),
            )
            refreshed = refresh_youtube_publish_task(
                db,
                task,
                client=FakePublishClient(
                    refreshed={
                        "id": "remote-1",
                        "task_status": "completed",
                        "youtube_video_id": "yt-1",
                        "updated_at": "2026-07-29T03:10:00Z",
                    }
                ),
            )
            uploaded = db.scalar(
                select(YoutubeUploadedVideo).where(
                    YoutubeUploadedVideo.youtube_video_id == "yt-1"
                )
            )

            self.assertEqual("succeeded", refreshed.status)
            self.assertIsNotNone(uploaded)
            self.assertEqual(task.id, uploaded.publish_task_id)
            self.assertEqual("native-video-1", uploaded.source_native_agent_video_id)
            self.assertEqual(
                1,
                db.query(YoutubePublishTask).filter_by(youtube_video_id="yt-1").count(),
            )

    def test_cancelled_with_retry_error_maps_to_failed(self) -> None:
        with self.Session() as db:
            user, channel, video = self.seed(db)
            task = create_youtube_publish_task(
                db,
                self.command(user, channel, video),
                client=FakePublishClient(),
            )
            refreshed = refresh_youtube_publish_task(
                db,
                task,
                client=FakePublishClient(
                    refreshed={
                        "id": "remote-1",
                        "task_status": "cancelled",
                        "last_run_error": "upload failed after 10 retries",
                    }
                ),
            )
            self.assertEqual("failed", refreshed.status)
