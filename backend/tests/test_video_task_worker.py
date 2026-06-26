import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AudioReference,
    FileAsset,
    GeneratedImage,
    GenerationTask,
    Style,
    TaskPanel,
    User,
    VideoTask,
    VideoTaskAudioSegment,
)
from app.models.enums import (
    FileAssetPurpose,
    GeneratedImageJobKind,
    GeneratedImageSourceType,
    GeneratedImageStatus,
    ImageCountMode,
    StorageBackend,
    StoryInputMode,
    StyleReferenceMode,
    StyleStatus,
    TaskStatus,
    UserRole,
    VideoTaskStatus,
    VideoTaskStepName,
)
from app.services.video_task_worker import process_video_task


class FakeVoiceClient:
    def upload_reference_voice(self, **kwargs):
        return "speech:custom:doodlestory"

    def generate_speech(self, **kwargs):
        return b"mp3-bytes", "audio/mpeg"


class FakeComicVideoClient:
    def submit_episode(self, *, episode, output_name, speed):
        self.episode = episode
        return "job_123"

    def poll_job(self, job_id, *, timeout_seconds, interval_seconds):
        return {"job_id": job_id, "status": "succeeded", "output_url": "/api/v1/outputs/final.mp4"}

    def download_output(self, output_url):
        return b"video-bytes"


class VideoTaskWorkerTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def create_video_task(self, *, reference_text: str | None = "参考声音文本") -> str:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash", role=UserRole.user)
        style = Style(
            name="漫画风",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="9:16",
            style_reference_mode=StyleReferenceMode.prompt,
            style_prompt="干净漫画风",
        )
        db.add_all([user, style])
        db.flush()
        audio_asset = FileAsset(
            purpose=FileAssetPurpose.audio_reference,
            storage_backend=StorageBackend.local,
            storage_key="audio-reference/ref.mp3",
            content_type="audio/mpeg",
            byte_size=12,
        )
        image_asset = FileAsset(
            purpose=FileAssetPurpose.generated_image,
            storage_backend=StorageBackend.local,
            storage_key="generated-image/panel.png",
            content_type="image/png",
            byte_size=12,
        )
        db.add_all([audio_asset, image_asset])
        db.flush()
        reference = AudioReference(
            owner_user_id=user.id,
            name="参考音色",
            reference_text=reference_text,
            asset_id=audio_asset.id,
        )
        source_task = GenerationTask(
            owner_user_id=user.id,
            display_title="小狗回家",
            original_text="一只小狗找到回家的路。",
            story_input_mode=StoryInputMode.original,
            image_count_mode=ImageCountMode.auto,
            style_id=style.id,
            style_name_snapshot=style.name,
            style_prompt_snapshot=style.style_prompt,
            image_model_name_snapshot=style.image_model_name,
            style_aspect_ratio_snapshot=style.aspect_ratio,
            style_reference_mode_snapshot=style.style_reference_mode,
            status=TaskStatus.succeeded,
            progress_current=4,
            progress_total=4,
        )
        db.add_all([reference, source_task])
        db.flush()
        panel = TaskPanel(
            task_id=source_task.id,
            panel_order=1,
            original_text_segment="一只小狗找到回家的路。",
            narration_text="一只小狗找到回家的路。",
        )
        db.add(panel)
        db.flush()
        image = GeneratedImage(
            task_id=source_task.id,
            panel_id=panel.id,
            owner_user_id=user.id,
            job_kind=GeneratedImageJobKind.panel_image,
            status=GeneratedImageStatus.succeeded,
            generation_number=1,
            is_current=True,
            source_type=GeneratedImageSourceType.initial,
            image_model_name_snapshot=style.image_model_name,
            asset_id=image_asset.id,
        )
        video_task = VideoTask(
            owner_user_id=user.id,
            source_task_id=source_task.id,
            audio_reference_id=reference.id,
            display_title=source_task.display_title,
            original_text=source_task.original_text,
            audio_reference_name_snapshot=reference.name,
            audio_reference_text_snapshot=reference.reference_text,
            audio_reference_asset_id_snapshot=audio_asset.id,
            status=VideoTaskStatus.ready_for_audio,
            current_step=VideoTaskStepName.generate_narration_audio,
            progress_current=1,
            progress_total=4,
        )
        db.add_all([image, video_task])
        db.commit()
        video_task_id = video_task.id
        db.close()
        return video_task_id

    @patch("app.services.video_task_worker.materialize_asset_to_local", return_value=Path("/tmp/fake-media"))
    @patch("app.services.video_task_worker.ComicVideoServiceClient", return_value=FakeComicVideoClient())
    @patch("app.services.video_task_worker.SiliconFlowVoiceClient", return_value=FakeVoiceClient())
    @patch("app.services.video_task_worker.save_binary_file")
    def test_process_video_task_generates_audio_segments_and_output_video(
        self,
        save_binary_file,
        _voice_client,
        _video_client,
        _materialize,
    ) -> None:
        save_binary_file.side_effect = [
            SimpleNamespace(
                storage_backend=StorageBackend.local,
                storage_key="generated-audio/panel.mp3",
                public_url=None,
                byte_size=9,
                checksum_sha256="audio-sha",
            ),
            SimpleNamespace(
                storage_backend=StorageBackend.local,
                storage_key="generated-video/final.mp4",
                public_url=None,
                byte_size=11,
                checksum_sha256="video-sha",
            ),
        ]
        video_task_id = self.create_video_task()

        with patch("app.services.video_task_worker.SessionLocal", self.Session):
            process_video_task(video_task_id)

        db = self.Session()
        video_task = db.get(VideoTask, video_task_id)
        segments = db.scalars(select(VideoTaskAudioSegment).where(VideoTaskAudioSegment.video_task_id == video_task_id)).all()
        self.assertEqual(VideoTaskStatus.succeeded, video_task.status)
        self.assertEqual(1, len(segments))
        self.assertIsNotNone(video_task.output_video_asset_id)
        self.assertEqual("job_123", video_task.video_provider_job_id)
        self.assertIn('"shots"', video_task.video_episode_json)
        self.assertEqual(FileAssetPurpose.generated_video, db.get(FileAsset, video_task.output_video_asset_id).purpose)

    @patch("app.services.video_task_worker.materialize_asset_to_local", return_value=Path("/tmp/fake-media"))
    @patch("app.services.video_task_worker.SiliconFlowVoiceClient", return_value=FakeVoiceClient())
    def test_process_video_task_fails_when_reference_text_missing(self, _voice_client, _materialize) -> None:
        video_task_id = self.create_video_task(reference_text=None)

        with patch("app.services.video_task_worker.SessionLocal", self.Session):
            with self.assertRaises(RuntimeError):
                process_video_task(video_task_id)

        db = self.Session()
        video_task = db.get(VideoTask, video_task_id)
        self.assertEqual(VideoTaskStatus.failed, video_task.status)
        self.assertIn("参考文本", video_task.error_message)


if __name__ == "__main__":
    unittest.main()
