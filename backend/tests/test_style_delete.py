import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.styles import delete_style
from app.core.database import Base
from app.models.entities import GenerationTask, Style, User
from app.models.enums import ImageCountMode, StyleStatus


class StyleDeleteTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

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


if __name__ == "__main__":
    unittest.main()
