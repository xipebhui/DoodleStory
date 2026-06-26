import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.pagination import Pagination
from app.api.styles import create_style, delete_reference_image, delete_style, list_style_options, update_style
from app.core.database import Base
from app.models.entities import FileAsset, GenerationTask, Style, StyleReferenceImage, TaskStyleReferenceImage, User
from app.models.enums import FileAssetPurpose, ImageCountMode, StorageBackend, StyleStatus, StyleReferenceMode
from app.schemas.style import StyleCreate, StyleOptionRead, StyleUpdate


class StyleDeleteTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_style_options_returns_lightweight_preview_payload(self) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash")
        asset = FileAsset(
            purpose=FileAssetPurpose.style_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="style_reference/preview.png",
            public_url="https://cdn.example.com/style_reference/preview.png",
            content_type="image/png",
            byte_size=10,
        )
        style = Style(
            name="轻量选项风格",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_reference_mode=StyleReferenceMode.image,
            style_prompt="很长的风格提示词" * 200,
        )
        reference = StyleReferenceImage(style=style, asset=asset, display_order=1)
        db.add_all([user, asset, style, reference])
        db.commit()

        result = list_style_options(
            user=user,
            db=db,
            pagination=Pagination(limit=20, offset=0),
            query=None,
            status_filter=StyleStatus.active,
        )

        self.assertNotIn("style_prompt", StyleOptionRead.model_fields)
        self.assertEqual(1, len(result.items))
        self.assertEqual(style.id, result.items[0].id)
        self.assertEqual(asset.id, result.items[0].preview_asset.id)

    def test_delete_referenced_style_soft_deletes(self) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash")
        style = Style(
            name="可删除风格",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_prompt="手绘漫画风",
        )
        db.add_all([user, style])
        db.flush()
        db.add(
            GenerationTask(
                owner_user_id=user.id,
                display_title="历史任务",
                original_text="故事正文",
                image_count_mode=ImageCountMode.auto,
                style_id=style.id,
                style_name_snapshot=style.name,
                style_prompt_snapshot=style.style_prompt,
                image_model_name_snapshot=style.image_model_name,
                style_aspect_ratio_snapshot=style.aspect_ratio,
            )
        )
        db.commit()

        result = delete_style(style.id, user, db)

        db.refresh(style)
        self.assertTrue(result.data["deleted"])
        self.assertIsNotNone(style.deleted_at)
        self.assertEqual(StyleStatus.disabled, style.status)
        self.assertIn("[deleted:", style.name)

    def test_delete_unreferenced_style_removes_row(self) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash")
        style = Style(
            name="未引用风格",
            status=StyleStatus.draft,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_prompt="手绘漫画风",
        )
        db.add_all([user, style])
        db.commit()
        style_id = style.id

        result = delete_style(style_id, user, db)

        self.assertTrue(result.data["deleted"])
        self.assertIsNone(db.scalar(select(Style).where(Style.id == style_id)))

    def test_delete_reference_image_keeps_asset_used_by_task_snapshot(self) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash")
        asset = FileAsset(
            purpose=FileAssetPurpose.style_reference,
            storage_backend=StorageBackend.qiniu,
            storage_key="style_reference/history.png",
            public_url="https://cdn.example.com/style_reference/history.png",
            content_type="image/png",
            byte_size=10,
        )
        style = Style(
            name="参考图风格",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_reference_mode=StyleReferenceMode.image,
            style_prompt="手绘漫画风",
            cover_asset=asset,
        )
        reference = StyleReferenceImage(style=style, asset=asset, display_order=1)
        task = GenerationTask(
            owner=user,
            display_title="历史任务",
            original_text="故事正文",
            image_count_mode=ImageCountMode.auto,
            style=style,
            style_name_snapshot=style.name,
            style_prompt_snapshot=style.style_prompt,
            image_model_name_snapshot=style.image_model_name,
            style_aspect_ratio_snapshot=style.aspect_ratio,
            style_reference_mode_snapshot=StyleReferenceMode.image,
        )
        task_snapshot = TaskStyleReferenceImage(task=task, asset=asset, reference_order=1)
        db.add_all([user, asset, style, reference, task, task_snapshot])
        db.commit()

        result = delete_reference_image(style.id, reference.id, user, db)

        self.assertTrue(result.data["deleted"])
        self.assertIsNone(db.scalar(select(StyleReferenceImage).where(StyleReferenceImage.id == reference.id)))
        self.assertIsNotNone(db.scalar(select(FileAsset).where(FileAsset.id == asset.id)))
        self.assertIsNotNone(
            db.scalar(select(TaskStyleReferenceImage).where(TaskStyleReferenceImage.id == task_snapshot.id))
        )

    def test_create_style_duplicate_name_returns_business_error(self) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash")
        db.add_all(
            [
                user,
                Style(
                    name="极简黑白简笔画",
                    status=StyleStatus.active,
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                    style_prompt="黑白线稿",
                ),
            ]
        )
        db.commit()

        with self.assertRaises(HTTPException) as context:
            create_style(
                StyleCreate(
                    name=" 极简黑白简笔画 ",
                    status=StyleStatus.active,
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                    style_prompt="黑白线稿",
                ),
                user,
                db,
            )

        self.assertEqual(400, context.exception.status_code)
        self.assertEqual("风格名称已存在，请换一个名称", context.exception.detail)

    def test_update_style_duplicate_name_returns_business_error(self) -> None:
        db = self.Session()
        user = User(email="owner@example.com", password_hash="hash")
        first = Style(
            name="已有风格",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_prompt="黑白线稿",
        )
        second = Style(
            name="待修改风格",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_prompt="水彩",
        )
        db.add_all([user, first, second])
        db.commit()

        with self.assertRaises(HTTPException) as context:
            update_style(second.id, StyleUpdate(name="已有风格"), user, db)

        self.assertEqual(400, context.exception.status_code)
        self.assertEqual("风格名称已存在，请换一个名称", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
