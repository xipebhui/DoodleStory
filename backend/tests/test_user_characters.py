import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.api.characters import create_character, fill_character_description_from_reference
from app.api.tasks import extract_character_names
from app.core.database import Base
from app.models.entities import FileAsset, GenerationTask, Style, TaskCharacter, TaskCharacterAppearance, TaskPanel, TaskPanelCharacterAppearance, User, UserCharacter
from app.models.enums import FileAssetPurpose, ImageCountMode, StorageBackend, StyleReferenceMode, StyleStatus, StoryInputMode, UserRole, WorkflowStatus
from app.schemas.character import CharacterNameExtractionRequest, StoryCharacterBindingCreate
from app.schemas.task import TaskCreate
from app.services.character_references import (
    build_panel_reference_pack,
    ensure_fixed_character_panel_links_by_name,
    persist_missing_generated_character_plans,
)
from app.services.llm import ExtractedCharacterNames, TaskCharacterPlan, extract_character_names_from_story
from app.services.task_creation import TaskCreationError, create_generation_task_record


class UserCharacterTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
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
    @patch("app.api.characters.describe_character_reference_image")
    def test_character_create_saves_first_and_schedules_reference_description(self, describe_reference, save_bytes) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash", role=UserRole.user)
        db.add(user)
        db.commit()
        save_bytes.return_value = SimpleNamespace(
            storage_backend=StorageBackend.local,
            storage_key="characters/auto.png",
            public_url=None,
            byte_size=10,
            checksum_sha256="sha256",
        )
        upload = UploadFile(filename="role.png", file=BytesIO(b"image-bytes"), headers={"content-type": "image/png"})
        background_tasks = BackgroundTasks()

        response = __import__("asyncio").run(
            create_character(
                background_tasks=background_tasks,
                name="妈妈",
                description="",
                file=upload,
                user=user,
                db=db,
            )
        )

        self.assertIsNone(response.data.description)
        describe_reference.assert_not_called()
        self.assertEqual(1, len(background_tasks.tasks))

    @patch("app.api.characters.CHARACTER_DESCRIPTION_RETRY_COUNT", 3)
    @patch("app.api.characters.sleep")
    @patch("app.api.characters.describe_character_reference_image")
    def test_background_reference_description_retries_and_updates_blank_description(self, describe_reference, sleep) -> None:
        db = self.Session()
        asset = FileAsset(
            purpose=FileAssetPurpose.user_character_reference,
            storage_backend=StorageBackend.local,
            storage_key="characters/mom.png",
            content_type="image/png",
            byte_size=10,
        )
        user = User(email="owner@example.com", password_hash="hash", role=UserRole.user)
        db.add_all([asset, user])
        db.flush()
        character = UserCharacter(
            owner_user_id=user.id,
            name="妈妈",
            reference_asset_id=asset.id,
            description=None,
        )
        db.add(character)
        db.commit()
        describe_reference.side_effect = [
            RuntimeError("temporary vl error"),
            SimpleNamespace(text="中年女性，短发，穿宽松针织衫。"),
        ]

        with patch("app.api.characters.SessionLocal", self.Session):
            fill_character_description_from_reference(
                character_id=character.id,
                content=b"image-bytes",
                content_type="image/png",
            )

        db.expire_all()
        refreshed = db.get(UserCharacter, character.id)
        self.assertEqual("中年女性，短发，穿宽松针织衫。", refreshed.description)
        self.assertEqual(2, describe_reference.call_count)
        sleep.assert_called_once_with(1)

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

    def test_fixed_character_task_still_persists_unbound_generated_characters(self) -> None:
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
            storage_key="characters/me.png",
            public_url="https://cdn.example.com/me.png",
            content_type="image/png",
            byte_size=10,
        )
        db.add_all([owner, style, asset])
        db.flush()
        user_character = UserCharacter(
            owner_user_id=owner.id,
            name="小李",
            reference_asset_id=asset.id,
            description="9岁男孩，短发，穿蓝色外套。",
        )
        db.add(user_character)
        db.commit()
        task = create_generation_task_record(
            db=db,
            user=owner,
            payload=TaskCreate(
                original_text="我看见妈妈躺在床上，爸爸沉默着。",
                story_input_mode=StoryInputMode.original,
                image_count_mode=ImageCountMode.auto,
                style_id=style.id,
                story_characters=[StoryCharacterBindingCreate(source_name="我", user_character_id=user_character.id)],
            ),
        )

        persisted = persist_missing_generated_character_plans(
            db,
            task,
            [
                TaskCharacterPlan(
                    character_key="character_1",
                    name="我",
                    description="重复的固定角色",
                    appearances=[
                        {
                            "appearance_key": "character_1_child",
                            "age_stage": "童年",
                            "visual_prompt": "重复的我",
                        }
                    ],
                ),
                TaskCharacterPlan(
                    character_key="character_2",
                    name="妈妈",
                    description="虚弱的母亲",
                    appearances=[
                        {
                            "appearance_key": "character_2_adult",
                            "age_stage": "成年",
                            "visual_prompt": "躺在床上的妈妈",
                        }
                    ],
                ),
                TaskCharacterPlan(
                    character_key="character_3",
                    name="爸爸",
                    description="沉默的父亲",
                    appearances=[
                        {
                            "appearance_key": "character_3_adult",
                            "age_stage": "成年",
                            "visual_prompt": "站在门边的爸爸",
                        }
                    ],
                ),
            ],
        )

        characters = {
            character.name: character
            for character in db.query(TaskCharacter).filter(TaskCharacter.task_id == task.id).all()
        }
        self.assertEqual(["妈妈", "爸爸"], [character.name for character in persisted])
        self.assertEqual({"我", "妈妈", "爸爸"}, set(characters))
        self.assertEqual(WorkflowStatus.succeeded, characters["我"].appearances[0].status)
        self.assertEqual(WorkflowStatus.queued, characters["妈妈"].appearances[0].status)
        self.assertEqual(WorkflowStatus.queued, characters["爸爸"].appearances[0].status)

    def test_fixed_character_panel_links_are_added_when_generated_links_exist(self) -> None:
        db = self.Session()
        owner = User(email="owner@example.com", password_hash="hash", role=UserRole.user)
        db.add(owner)
        db.flush()
        task = GenerationTask(
            owner_user_id=owner.id,
            display_title="任务",
            original_text="我和妈妈在房间里。",
            story_input_mode=StoryInputMode.adapted,
            image_count_mode=ImageCountMode.auto,
            use_character_references=True,
            style_id="style",
            style_name_snapshot="风格",
            style_prompt_snapshot="温暖绘本风",
            image_model_name_snapshot="gpt-image-2",
            style_aspect_ratio_snapshot="9:16",
            style_reference_mode_snapshot=StyleReferenceMode.prompt,
        )
        db.add(task)
        db.flush()
        fixed = TaskCharacter(task_id=task.id, character_key="fixed_1", name="我", description="9岁男孩")
        generated = TaskCharacter(task_id=task.id, character_key="character_2", name="妈妈", description="母亲")
        db.add_all([fixed, generated])
        db.flush()
        fixed_appearance = TaskCharacterAppearance(
            task_character_id=fixed.id,
            appearance_key="fixed_1_default",
            age_stage="固定角色",
            visual_prompt="9岁男孩",
            reference_image_id="asset-fixed",
            status=WorkflowStatus.succeeded,
        )
        generated_appearance = TaskCharacterAppearance(
            task_character_id=generated.id,
            appearance_key="character_2_adult",
            age_stage="成年",
            visual_prompt="母亲",
            reference_image_id="asset-generated",
            status=WorkflowStatus.succeeded,
        )
        panel = TaskPanel(task_id=task.id, panel_order=1, original_text_segment="我和妈妈在房间里。", generated_prompt="我站在妈妈身边。")
        db.add_all([fixed_appearance, generated_appearance, panel])
        db.flush()
        db.add(
            TaskPanelCharacterAppearance(
                panel_id=panel.id,
                task_character_appearance_id=generated_appearance.id,
                reference_order=1,
            )
        )
        db.commit()
        db.expire_all()
        task = db.get(GenerationTask, task.id)
        self.assertIsNotNone(task)

        ensure_fixed_character_panel_links_by_name(db, task)

        links = (
            db.query(TaskPanelCharacterAppearance)
            .filter(TaskPanelCharacterAppearance.panel_id == panel.id)
            .order_by(TaskPanelCharacterAppearance.reference_order.asc())
            .all()
        )
        self.assertEqual([generated_appearance.id, fixed_appearance.id], [link.task_character_appearance_id for link in links])
        self.assertEqual([1, 2], [link.reference_order for link in links])

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
