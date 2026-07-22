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
    get_agent_run,
    list_agent_conversations,
)
from app.api.pagination import Pagination
from app.core.database import Base
from app.models.entities import AgentMessage, AgentRun, Style, User
from app.models.enums import StyleStatus
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
        self.db.add_all([self.owner, self.other])
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


if __name__ == "__main__":
    unittest.main()
