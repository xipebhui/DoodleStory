from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    FileAsset,
    NativeAgentConversation,
    NativeAgentRun,
    NativeAgentVideo,
    PublishableVideo,
    User,
)
from app.models.enums import AgentSkillStatus, FileAssetPurpose, StorageBackend, UserRole
from app.services.reviewed_local_video_publication import (
    ReviewedVideoFacts,
    load_reviewed_video_facts,
    rank_normal_channels,
    register_reviewed_video,
)
from app.services.storage import StoredFile


class FakePublisher:
    def list_channels(self):
        return [
            {"channel_id": "UC-B", "title": "B", "status": "normal"},
            {"channel_id": "UC-X", "title": "X", "status": "banned"},
            {"channel_id": "UC-A", "title": "A", "status": "normal"},
        ]

    def channel_videos(self, channel_id: str):
        return {
            "UC-A": [{"id": "1"}],
            "UC-B": [{"id": "1"}],
        }[channel_id]


class ReviewedVideoFactsTests(unittest.TestCase):
    def test_rank_channels_filters_status_and_uses_channel_id_tie_break(self) -> None:
        ranked = rank_normal_channels(FakePublisher())

        self.assertEqual(["UC-A", "UC-B"], [item.channel_id for item in ranked])
        self.assertEqual([1, 1], [item.published_video_count for item in ranked])

    def test_acceptance_requires_exact_bytes_path_and_media_facts(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "storage" / "final.mp4"
            video.parent.mkdir(parents=True)
            content = b"reviewed-video-bytes"
            video.write_bytes(content)
            acceptance = root / "docs" / "acceptance.json"
            acceptance.parent.mkdir(parents=True)
            acceptance.write_text(
                json.dumps(
                    {
                        "status": "ready_for_user_manual_upload_footerless",
                        "render": {
                            "video": "storage/final.mp4",
                            "sha256": hashlib.sha256(content).hexdigest(),
                            "bytes": len(content),
                            "duration_ms": 39061,
                            "frames": 1170,
                            "width": 1920,
                            "height": 1080,
                            "fps": 30,
                            "video_codec": "h264",
                            "audio_codec": "aac",
                            "pixel_format": "yuv420p",
                        },
                    }
                ),
                encoding="utf-8",
            )
            probe = {
                "format": {"duration": "39.061"},
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "pix_fmt": "yuv420p",
                        "width": 1920,
                        "height": 1080,
                        "avg_frame_rate": "30/1",
                        "nb_read_frames": "1170",
                    },
                    {"codec_type": "audio", "codec_name": "aac"},
                ],
            }

            with patch(
                "app.services.reviewed_local_video_publication._ffprobe",
                return_value=probe,
            ):
                facts = load_reviewed_video_facts(
                    root,
                    acceptance_path=acceptance,
                    video_path=video,
                )

            self.assertEqual(hashlib.sha256(content).hexdigest(), facts.checksum_sha256)
            self.assertEqual("docs/acceptance.json", facts.acceptance_path)
            self.assertEqual("storage/final.mp4", facts.source_video_path)


class ReviewedVideoRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    @staticmethod
    def seed(db):
        owner = User(
            email="admin@example.com",
            password_hash="hash",
            role=UserRole.admin,
        )
        db.add(owner)
        db.flush()
        skill = AgentSkill(
            owner_user_id=None,
            slug="reviewed-import-test",
            name="Paynes Creek S03 import test",
            description="test",
            draft_instructions="test",
            draft_tool_names_json="[]",
            draft_revision=1,
            status=AgentSkillStatus.published,
        )
        db.add(skill)
        db.flush()
        version = AgentSkillVersion(
            skill_id=skill.id,
            version=1,
            name_snapshot=skill.name,
            description_snapshot=skill.description,
            instructions=skill.draft_instructions,
            tool_names_json="[]",
            content_hash="sha256:test",
            publish_idempotency_key="test",
            published_by_user_id=owner.id,
            published_at=datetime.utcnow(),
        )
        db.add(version)
        db.commit()
        return owner, version

    def test_registration_is_idempotent_and_preserves_trace(self) -> None:
        facts = ReviewedVideoFacts(
            acceptance_path="docs/testing/acceptance.json",
            source_video_path="storage/final.mp4",
            checksum_sha256="a" * 64,
            byte_size=4,
            duration_ms=1000,
            frames=30,
            width=1920,
            height=1080,
            fps=30,
            video_codec="h264",
            audio_codec="aac",
            pixel_format="yuv420p",
        )
        with TemporaryDirectory() as temporary:
            video_path = Path(temporary) / "final.mp4"
            video_path.write_bytes(b"test")

            def store_file(purpose: str, content: bytes, suffix: str) -> StoredFile:
                self.assertEqual(FileAssetPurpose.generated_video.value, purpose)
                self.assertEqual(b"test", content)
                self.assertEqual(".mp4", suffix)
                return StoredFile(
                    StorageBackend.aliyun_oss,
                    "generated_video/test.mp4",
                    4,
                    "a" * 64,
                    "https://cdn.example/generated_video/test.mp4",
                )

            with self.Session() as db:
                owner, version = self.seed(db)
                with (
                    patch(
                        "app.services.reviewed_local_video_publication.asset_content_url",
                        return_value="https://cdn.example/generated_video/test.mp4",
                    ),
                    patch(
                        "app.services.reviewed_local_video_publication._verify_public_video_url"
                    ),
                ):
                    first = register_reviewed_video(
                        db,
                        owner=owner,
                        skill_version=version,
                        facts=facts,
                        video_path=video_path,
                        source_git_commit="b" * 40,
                        title="Title",
                        description="Description",
                        tags=["tag"],
                        store_file=store_file,
                    )
                    second = register_reviewed_video(
                        db,
                        owner=owner,
                        skill_version=version,
                        facts=facts,
                        video_path=video_path,
                        source_git_commit="b" * 40,
                        title="Title",
                        description="Description",
                        tags=["tag"],
                        store_file=store_file,
                    )

                self.assertEqual(first[0].id, second[0].id)
                self.assertEqual(first[1].id, second[1].id)
                self.assertEqual(first[2].id, second[2].id)
                self.assertEqual(
                    1, db.scalar(select(func.count()).select_from(FileAsset))
                )
                self.assertEqual(
                    1,
                    db.scalar(select(func.count()).select_from(NativeAgentConversation)),
                )
                self.assertEqual(
                    1, db.scalar(select(func.count()).select_from(NativeAgentRun))
                )
                self.assertEqual(
                    1, db.scalar(select(func.count()).select_from(NativeAgentVideo))
                )
                self.assertEqual(
                    1, db.scalar(select(func.count()).select_from(PublishableVideo))
                )
                provenance = json.loads(first[1].scenes_json)
                self.assertEqual("reviewed_local_video_import", provenance[0]["kind"])
                self.assertEqual(0, first[1].run.model_call_count)


if __name__ == "__main__":
    unittest.main()
