import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.characters import create_character
from app.api.tasks import extract_character_names
from app.core.database import Base
from app.models.entities import FileAsset, Style, TaskPanel, TaskPanelCharacterAppearance, User, UserCharacter
from app.models.enums import FileAssetPurpose, ImageCountMode, StorageBackend, StyleReferenceMode, StyleStatus, StoryInputMode, UserRole, WorkflowStatus
from app.schemas.character import CharacterNameExtractionRequest, StoryCharacterBindingCreate
from app.schemas.task import TaskCreate
from app.services.character_references import build_panel_reference_pack
from app.services.llm import ExtractedCharacterNames, extract_character_names_from_story
from app.services.task_creation import TaskCreationError, create_generation_task_record


class UserCharacterTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    @patch("app.services.llm.call_siliconflow_json")
    @patch("app.services.llm.get_settings")
    def test_ai_extraction_uses_character_model_and_normalizes_names(self, get_settings, call_json) -> None:
        get_settings.return_value = SimpleNamespace(
            character_extraction_model="Qwen/Qwen3.6-27B",
            character_extraction_temperature=0.1,
        )
        call_json.return_value = {"names": [" 三只小猪 ", "小猪", "大灰狼", "大灰狼"]}

        result = extract_character_names_from_story(text="三只小猪盖房子，大灰狼来敲门。")

        self.assertEqual(["三只小猪", "大灰狼"], result.names)
        call_json.assert_called_once()
        self.assertEqual("Qwen/Qwen3.6-27B", call_json.call_args.kwargs["model"])
        self.assertEqual(0.1, call_json.call_args.kwargs["temperature"])

    @patch("app.api.tasks.extract_character_names_from_story")
    def test_character_extraction_api_returns_names_payload(self, extract_from_story) -> None:
        extract_from_story.return_value = ExtractedCharacterNames(names=["我", "妈妈", "爸爸"])
        user = User(email="owner@example.com", password_hash="hash", role=UserRole.user)

        response = extract_character_names(
            CharacterNameExtractionRequest(text="我看见妈妈躺在床上，爸爸沉默着。"),
            user,
        )

        self.assertEqual(["我", "妈妈", "爸爸"], response.data.names)

    @patch("app.api.characters.save_bytes")
    @patch("app.api.characters.describe_reference_or_502")
    def test_character_create_auto_fills_description_from_reference_image(self, describe_reference, save_bytes) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash", role=UserRole.user)
        db.add(user)
        db.commit()
        describe_reference.return_value = "中年女性，短发，穿宽松针织衫；保持发型、体态和服装轮廓不变。"
        save_bytes.return_value = SimpleNamespace(
            storage_backend=StorageBackend.local,
            storage_key="characters/auto.png",
            public_url=None,
            byte_size=10,
            checksum_sha256="sha256",
        )
        upload = UploadFile(filename="role.png", file=BytesIO(b"image-bytes"), headers={"content-type": "image/png"})

        response = __import__("asyncio").run(
            create_character(
                name="妈妈",
                description="",
                file=upload,
                user=user,
                db=db,
            )
        )

        self.assertEqual(describe_reference.return_value, response.data.description)
        describe_reference.assert_called_once_with(b"image-bytes", "image/png")

    def test_task_can_only_bind_owned_user_character(self) -> None:
        db = self.Session()
        owner = User(email="owner@example.com", password_hash="hash", role=UserRole.user)
        other = User(email="other@example.com", password_hash="hash", role=UserRole.user)
        style = Style(
            name="绘本",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="9:16",
            style_reference_mode=StyleReferenceMode.prompt,
            style_prompt="温暖绘本风",
        )
        owned_asset = FileAsset(
            purpose=FileAssetPurpose.user_character_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="characters/owned.png",
            public_url="https://cdn.example.com/owned.png",
            content_type="image/png",
            byte_size=10,
        )
        other_asset = FileAsset(
            purpose=FileAssetPurpose.user_character_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="characters/other.png",
            public_url="https://cdn.example.com/other.png",
            content_type="image/png",
            byte_size=10,
        )
        db.add_all([owner, other, style, owned_asset, other_asset])
        db.flush()
        owned_character = UserCharacter(
            owner_user_id=owner.id,
            name="小猪",
            reference_asset_id=owned_asset.id,
            description="圆滚滚的小猪",
        )
        other_character = UserCharacter(
            owner_user_id=other.id,
            name="狼",
            reference_asset_id=other_asset.id,
            description="灰色的狼",
        )
        db.add_all([owned_character, other_character])
        db.commit()

        task = create_generation_task_record(
            db=db,
            user=owner,
            payload=TaskCreate(
                original_text="三只小猪盖房子。",
                story_input_mode=StoryInputMode.original,
                image_count_mode=ImageCountMode.auto,
                style_id=style.id,
                story_characters=[
                    StoryCharacterBindingCreate(source_name="三只小猪", user_character_id=owned_character.id)
                ],
            ),
        )
        self.assertTrue(task.use_character_references)
        self.assertEqual(1, len(task.characters))
        self.assertEqual(WorkflowStatus.succeeded, task.characters[0].appearances[0].status)
        self.assertEqual(owned_asset.id, task.characters[0].appearances[0].reference_image_id)
        self.assertIn("圆滚滚的小猪", task.characters[0].appearances[0].visual_prompt)

        with self.assertRaisesRegex(TaskCreationError, "当前用户自己的角色"):
            create_generation_task_record(
                db=db,
                user=owner,
                payload=TaskCreate(
                    original_text="狼来了。",
                    story_input_mode=StoryInputMode.original,
                    image_count_mode=ImageCountMode.auto,
                    style_id=style.id,
                    story_characters=[
                        StoryCharacterBindingCreate(source_name="狼", user_character_id=other_character.id)
                    ],
                ),
            )

    def test_panel_reference_pack_includes_character_anchor_and_priority(self) -> None:
        db = self.Session()
        owner = User(email="owner@example.com", password_hash="hash", role=UserRole.user)
        style = Style(
            name="绘本",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="9:16",
            style_reference_mode=StyleReferenceMode.prompt,
            style_prompt="温暖绘本风",
        )
        asset = FileAsset(
            purpose=FileAssetPurpose.user_character_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="characters/mom.png",
            public_url="https://cdn.example.com/mom.png",
            content_type="image/png",
            byte_size=10,
        )
        db.add_all([owner, style, asset])
        db.flush()
        user_character = UserCharacter(
            owner_user_id=owner.id,
            name="妈妈",
            reference_asset_id=asset.id,
            description="中年女性，短发，穿宽松针织衫；保持服装轮廓不变。",
        )
        db.add(user_character)
        db.commit()
        task = create_generation_task_record(
            db=db,
            user=owner,
            payload=TaskCreate(
                original_text="妈妈躺在床上织毛裤。",
                story_input_mode=StoryInputMode.original,
                image_count_mode=ImageCountMode.auto,
                style_id=style.id,
                story_characters=[
                    StoryCharacterBindingCreate(source_name="妈妈", user_character_id=user_character.id)
                ],
            ),
        )
        panel = TaskPanel(task_id=task.id, panel_order=1, original_text_segment="妈妈躺在床上织毛裤。")
        db.add(panel)
        db.flush()
        db.add(
            TaskPanelCharacterAppearance(
                panel_id=panel.id,
                task_character_appearance_id=task.characters[0].appearances[0].id,
                reference_order=1,
            )
        )
        db.commit()

        pack = build_panel_reference_pack(panel=panel)

        self.assertEqual(1, pack.character_count)
        self.assertIn("固定角色参考（参考图1）：妈妈", pack.notes[0])
        self.assertIn("中年女性，短发", pack.notes[0])
        self.assertIn("固定角色身份 > 当前剧情动作/情绪 > 风格表现方式 > 风格模板默认人物外观", pack.notes[0])


if __name__ == "__main__":
    unittest.main()
