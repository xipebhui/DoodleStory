import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import FileAsset, Style, User, UserCharacter
from app.models.enums import FileAssetPurpose, ImageCountMode, StorageBackend, StyleReferenceMode, StyleStatus, StoryInputMode, UserRole, WorkflowStatus
from app.schemas.character import StoryCharacterBindingCreate
from app.schemas.task import TaskCreate
from app.services.llm import extract_character_names_from_story
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


if __name__ == "__main__":
    unittest.main()
