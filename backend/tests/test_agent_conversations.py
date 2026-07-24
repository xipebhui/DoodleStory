import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.agent_conversations import (
    create_agent_conversation,
    create_agent_message,
    get_agent_conversation,
    get_agent_conversation_task,
    get_agent_run,
    list_agent_conversations,
)
from app.api.pagination import Pagination
from app.core.database import Base
from app.models.entities import (
    AgentMessage,
    AgentRun,
    FileAsset,
    GeneratedImage,
    GenerationTask,
    Style,
    TaskPanel,
    User,
)
from app.models.enums import (
    AgentRunStatus,
    FileAssetPurpose,
    GeneratedImageSourceType,
    GeneratedImageStatus,
    ImageCountMode,
    StorageBackend,
    StoryInputMode,
    StyleStatus,
    TaskStatus,
    UserRole,
)
from app.schemas.agent import (
    AgentConversationCreate,
    AgentMessageCreate,
    AgentResourceKind,
    AgentResourceRef,
)


class AgentConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        self.owner = User(email="agent-owner@example.com", password_hash="hash")
        self.other = User(email="agent-other@example.com", password_hash="hash")
        self.admin = User(
            email="agent-admin@example.com",
            password_hash="hash",
            role=UserRole.admin,
        )
        self.db.add_all([self.owner, self.other, self.admin])
        self.db.commit()
        self.style = Style(
            name="水彩",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_prompt="清透水彩漫画",
        )
        self.db.add(self.style)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def create_conversation(self, title: str = "测试会话"):
        return create_agent_conversation(
            AgentConversationCreate(title=title),
            user=self.owner,
            db=self.db,
        ).data

    def create_task(self, owner: User | None = None, title: str = "Agent 漫画") -> GenerationTask:
        task = GenerationTask(
            owner_user_id=(owner or self.owner).id,
            display_title=title,
            original_text="真实故事",
            story_input_mode=StoryInputMode.original,
            image_count_mode=ImageCountMode.fixed,
            requested_image_count=2,
            style_id=self.style.id,
            style_name_snapshot=self.style.name,
            style_prompt_snapshot=self.style.style_prompt,
            image_model_name_snapshot=self.style.image_model_name,
            style_aspect_ratio_snapshot=self.style.aspect_ratio,
            status=TaskStatus.succeeded,
            progress_current=2,
            progress_total=2,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def create_image(
        self,
        task: GenerationTask,
        panel: TaskPanel,
        generation_number: int,
        *,
        is_current: bool,
        status_value: GeneratedImageStatus = GeneratedImageStatus.succeeded,
    ) -> GeneratedImage:
        asset = None
        if status_value == GeneratedImageStatus.succeeded:
            asset = FileAsset(
                purpose=FileAssetPurpose.generated_image,
                storage_backend=StorageBackend.local,
                storage_key=f"agent-test/{panel.id}-{generation_number}.png",
                content_type="image/png",
                byte_size=128,
                width=900,
                height=1200,
            )
            self.db.add(asset)
            self.db.flush()
        image = GeneratedImage(
            task_id=task.id,
            panel_id=panel.id,
            owner_user_id=task.owner_user_id,
            status=status_value,
            generation_number=generation_number,
            is_current=is_current,
            source_type=(
                GeneratedImageSourceType.initial
                if generation_number == 1
                else GeneratedImageSourceType.user_edit
            ),
            image_model_name_snapshot=task.image_model_name_snapshot,
            asset_id=asset.id if asset else None,
        )
        self.db.add(image)
        return image

    def test_create_list_and_bounded_detail_are_owner_scoped(self):
        first = self.create_conversation("第一条")
        second = self.create_conversation("第二条")

        page = list_agent_conversations(
            user=self.owner,
            db=self.db,
            pagination=Pagination(limit=1, offset=0),
        )

        self.assertEqual(1, len(page.items))
        self.assertTrue(page.page.has_more)
        self.assertIn(page.items[0].id, {first.id, second.id})
        detail = get_agent_conversation(
            first.id,
            user=self.owner,
            db=self.db,
            message_limit=10,
            message_cursor=0,
        )
        self.assertEqual([], detail.data.messages)
        with self.assertRaises(HTTPException) as raised:
            get_agent_conversation(
                first.id,
                user=self.other,
                db=self.db,
                message_limit=10,
                message_cursor=0,
            )
        self.assertEqual(404, raised.exception.status_code)

    def test_send_message_persists_exact_content_resources_and_queued_run(self):
        conversation = self.create_conversation()
        payload = AgentMessageCreate(
            content="  保留用户原始空格  ",
            resource_refs=[
                AgentResourceRef(kind=AgentResourceKind.style, id=self.style.id, display_name="旧名称")
            ],
        )

        with patch("app.api.agent_conversations.enqueue_agent_run", new=AsyncMock()) as enqueue:
            accepted = asyncio.run(
                create_agent_message(
                    conversation.id,
                    payload,
                    user=self.owner,
                    db=self.db,
                )
            ).data

        enqueue.assert_awaited_once_with(accepted.run.id)
        self.assertEqual("  保留用户原始空格  ", accepted.message.content)
        self.assertEqual(self.style.id, accepted.message.resource_refs[0].id)
        self.assertEqual("水彩", accepted.message.resource_refs[0].display_name)
        saved_message = self.db.get(AgentMessage, accepted.message.id)
        saved_run = self.db.get(AgentRun, accepted.run.id)
        self.assertEqual("  保留用户原始空格  ", saved_message.content)
        self.assertEqual("queued", saved_run.status.value)

        run_response = get_agent_run(accepted.run.id, user=self.owner, db=self.db)
        self.assertEqual(accepted.run.id, run_response.data.id)
        with self.assertRaises(HTTPException) as raised:
            get_agent_run(accepted.run.id, user=self.other, db=self.db)
        self.assertEqual(404, raised.exception.status_code)

    def test_rejects_unknown_style_resource_before_creating_run(self):
        conversation = self.create_conversation()
        payload = AgentMessageCreate(
            content="创建两格漫画",
            resource_refs=[
                AgentResourceRef(kind=AgentResourceKind.style, id="not-owned-or-visible")
            ],
        )

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                create_agent_message(
                    conversation.id,
                    payload,
                    user=self.owner,
                    db=self.db,
                )
            )

        self.assertEqual(403, raised.exception.status_code)
        self.assertEqual(0, len(self.db.scalars(select(AgentRun)).all()))

    def test_rejects_second_message_while_turn_is_pending(self):
        conversation = self.create_conversation()
        with patch("app.api.agent_conversations.enqueue_agent_run", new=AsyncMock()):
            asyncio.run(
                create_agent_message(
                    conversation.id,
                    AgentMessageCreate(content="first"),
                    user=self.owner,
                    db=self.db,
                )
            )
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    create_agent_message(
                        conversation.id,
                        AgentMessageCreate(content="second"),
                        user=self.owner,
                        db=self.db,
                    )
                )
        self.assertEqual(409, raised.exception.status_code)

    def test_conversation_task_inspector_is_owner_scoped_and_requires_link(self):
        conversation = self.create_conversation()
        linked_task = self.create_task()
        unrelated_task = self.create_task(title="无关任务")
        wrong_owner_task = self.create_task(owner=self.other, title="其他用户任务")
        self.db.add(
            AgentRun(
                conversation_id=conversation.id,
                turn_id="linked-turn",
                task_id=linked_task.id,
                status=AgentRunStatus.succeeded,
            )
        )
        self.db.add(
            AgentRun(
                conversation_id=conversation.id,
                turn_id="wrong-owner-turn",
                task_id=wrong_owner_task.id,
                status=AgentRunStatus.succeeded,
            )
        )
        self.db.commit()

        response = get_agent_conversation_task(
            conversation.id,
            linked_task.id,
            user=self.owner,
            db=self.db,
        )
        self.assertEqual(linked_task.id, response.data.task_id)

        for denied_user in (self.other, self.admin):
            with self.assertRaises(HTTPException) as raised:
                get_agent_conversation_task(
                    conversation.id,
                    linked_task.id,
                    user=denied_user,
                    db=self.db,
                )
            self.assertEqual(404, raised.exception.status_code)

        with self.assertRaises(HTTPException) as raised:
            get_agent_conversation_task(
                conversation.id,
                unrelated_task.id,
                user=self.owner,
                db=self.db,
            )
        self.assertEqual(404, raised.exception.status_code)
        with self.assertRaises(HTTPException) as raised:
            get_agent_conversation_task(
                conversation.id,
                wrong_owner_task.id,
                user=self.owner,
                db=self.db,
            )
        self.assertEqual(404, raised.exception.status_code)

    def test_conversation_task_inspector_sorts_panels_and_bounds_versions(self):
        conversation = self.create_conversation()
        task = self.create_task()
        second_panel = TaskPanel(
            task_id=task.id,
            panel_order=2,
            original_text_segment="第二格",
            text_layout="结尾画面",
        )
        first_panel = TaskPanel(
            task_id=task.id,
            panel_order=1,
            original_text_segment="第一格",
            text_layout="开场画面",
        )
        third_panel = TaskPanel(
            task_id=task.id,
            panel_order=3,
            original_text_segment="第三格",
            text_layout="尚未选定当前版本",
        )
        self.db.add_all([second_panel, first_panel, third_panel])
        self.db.flush()
        current_image = None
        for generation_number in range(1, 23):
            image = self.create_image(
                task,
                first_panel,
                generation_number,
                is_current=generation_number == 2,
            )
            if generation_number == 2:
                current_image = image
        self.create_image(task, second_panel, 1, is_current=True)
        self.create_image(task, third_panel, 1, is_current=False)
        self.db.add(
            AgentRun(
                conversation_id=conversation.id,
                turn_id="ordered-turn",
                task_id=task.id,
                status=AgentRunStatus.succeeded,
            )
        )
        self.db.commit()

        response = get_agent_conversation_task(
            conversation.id,
            task.id,
            user=self.owner,
            db=self.db,
        ).data

        self.assertEqual([1, 2, 3], [panel.panel_order for panel in response.panels])
        first = response.panels[0]
        self.assertEqual(2, first.current_image.generation_number)
        self.assertEqual(20, len(first.versions))
        self.assertEqual(
            list(range(22, 2, -1)),
            [version.generation_number for version in first.versions],
        )
        self.assertIsNone(response.panels[2].current_image)
        self.assertEqual(1, response.panels[2].versions[0].generation_number)
        detail = get_agent_conversation(
            conversation.id,
            user=self.owner,
            db=self.db,
            message_limit=10,
            message_cursor=0,
        ).data
        self.assertEqual(current_image.id, detail.task_cards[0].panels[0].image.id)


if __name__ == "__main__":
    unittest.main()
