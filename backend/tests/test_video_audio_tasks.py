import asyncio
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.audio_references import create_audio_reference, transcribe_audio_reference
from app.api.video_tasks import create_video_task, get_video_task
from app.core.database import Base
from app.models.entities import AudioReference, FileAsset, Style, User, VideoTask
from app.models.enums import (
    FileAssetPurpose,
    ImageCountMode,
    StorageBackend,
    StyleReferenceMode,
    StyleStatus,
    TaskStatus,
    UserRole,
    VideoTaskStatus,
)
from app.schemas.video_task import VideoTaskCreate
from app.services.local_whisper import normalize_transcription_text


class VideoAudioTaskTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def create_user_and_style(self):
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
        db.commit()
        return db, user, style

    @patch("app.api.audio_references.save_binary_file")
    def test_create_audio_reference_saves_audio_asset(self, save_binary_file) -> None:
        db, user, _ = self.create_user_and_style()
        save_binary_file.return_value = SimpleNamespace(
            storage_backend=StorageBackend.local,
            storage_key="audio-reference/test.mp3",
            public_url=None,
            byte_size=12,
            checksum_sha256="sha256",
        )
        upload = UploadFile(filename="voice.mp3", file=BytesIO(b"audio-bytes"), headers={"content-type": "audio/mpeg"})

        response = asyncio.run(
            create_audio_reference(
                name="温柔女声",
                description="测试音色",
                reference_text="你好，欢迎来到故事里。",
                voice_provider="siliconflow",
                voice_model="FunAudioLLM/CosyVoice2-0.5B",
                voice_name="FunAudioLLM/CosyVoice2-0.5B:alex",
                file=upload,
                user=user,
                db=db,
            )
        )

        self.assertEqual("温柔女声", response.data.name)
        self.assertEqual(FileAssetPurpose.audio_reference, db.get(FileAsset, response.data.asset.id).purpose)
        self.assertEqual("audio/mpeg", response.data.asset.content_type)
        self.assertEqual("你好，欢迎来到故事里。", response.data.reference_text)

    def test_create_audio_reference_requires_transcribed_text(self) -> None:
        db, user, _ = self.create_user_and_style()
        upload = UploadFile(filename="voice.mp3", file=BytesIO(b"audio-bytes"), headers={"content-type": "audio/mpeg"})

        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                create_audio_reference(
                    name="温柔女声",
                    description="测试音色",
                    reference_text="",
                    file=upload,
                    user=user,
                    db=db,
                )
            )

        self.assertEqual("参考音频必须先完成本地转写", context.exception.detail)

    @patch("app.api.audio_references.transcribe_audio_content", return_value="自动识别出的参考文本")
    def test_transcribe_audio_reference_returns_local_whisper_text(self, transcribe_audio_content) -> None:
        db, user, _ = self.create_user_and_style()
        upload = UploadFile(filename="voice.wav", file=BytesIO(b"audio-bytes"), headers={"content-type": "audio/wav"})

        response = asyncio.run(transcribe_audio_reference(file=upload, _user=user))

        self.assertEqual("自动识别出的参考文本", response.data.text)
        transcribe_audio_content.assert_called_once_with(b"audio-bytes", ".wav")

    def test_local_whisper_transcription_is_normalized_to_simplified_chinese(self) -> None:
        self.assertEqual("电台测试，欢迎来到故事里。", normalize_transcription_text("電臺測試，歡迎來到故事裡。"))

    @patch("app.api.video_tasks.enqueue_task", new_callable=AsyncMock)
    def test_create_video_task_creates_real_source_generation_task(self, enqueue_task) -> None:
        db, user, style = self.create_user_and_style()
        audio_asset = FileAsset(
            purpose=FileAssetPurpose.audio_reference,
            storage_backend=StorageBackend.local,
            storage_key="audio-reference/ref.mp3",
            content_type="audio/mpeg",
            byte_size=12,
        )
        db.add(audio_asset)
        db.flush()
        reference = AudioReference(
            owner_user_id=user.id,
            name="温柔女声",
            reference_text="参考文本",
            asset_id=audio_asset.id,
        )
        db.add(reference)
        db.commit()

        response = asyncio.run(
            create_video_task(
                VideoTaskCreate(
                    original_text="小女孩在雨里捡到一把发光的伞。",
                    image_count_mode=ImageCountMode.auto,
                    requested_image_count=None,
                    style_id=style.id,
                    audio_reference_id=reference.id,
                ),
                user=user,
                db=db,
            )
        )

        video_task = db.scalar(select(VideoTask).where(VideoTask.id == response.data.id))
        self.assertEqual(VideoTaskStatus.waiting_for_images, video_task.status)
        self.assertEqual("温柔女声", video_task.audio_reference_name_snapshot)
        self.assertEqual("参考文本", video_task.audio_reference_text_snapshot)
        self.assertEqual("小女孩在雨里捡到一把发光的伞。", video_task.source_task.original_text)
        self.assertEqual(style.id, video_task.source_task.style_id)
        enqueue_task.assert_awaited_once_with(video_task.source_task_id)

    def test_video_task_syncs_ready_when_source_task_succeeds(self) -> None:
        db, user, style = self.create_user_and_style()
        audio_asset = FileAsset(
            purpose=FileAssetPurpose.audio_reference,
            storage_backend=StorageBackend.local,
            storage_key="audio-reference/ref.mp3",
            content_type="audio/mpeg",
            byte_size=12,
        )
        db.add(audio_asset)
        db.flush()
        reference = AudioReference(owner_user_id=user.id, name="温柔女声", asset_id=audio_asset.id)
        db.add(reference)
        db.commit()
        with patch("app.api.video_tasks.enqueue_task", new_callable=AsyncMock):
            created = asyncio.run(
                create_video_task(
                    VideoTaskCreate(
                        original_text="一只小狗找到回家的路。",
                        style_id=style.id,
                        audio_reference_id=reference.id,
                    ),
                    user=user,
                    db=db,
                )
            )
        video_task = db.get(VideoTask, created.data.id)
        video_task.source_task.status = TaskStatus.succeeded
        db.commit()

        response = get_video_task(video_task.id, user=user, db=db)

        self.assertEqual(VideoTaskStatus.ready_for_audio, response.data.status)
        self.assertEqual("generate_narration_audio", response.data.current_step)
        self.assertEqual(1, response.data.progress_current)


if __name__ == "__main__":
    unittest.main()
