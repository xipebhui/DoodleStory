import unittest

from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import AgentConversation, AgentEvent, AgentRun, User
from app.models.enums import (
    AgentApprovalStatus,
    AgentArtifactStatus,
    AgentEventType,
    AgentRunStatus,
)
from app.schemas.agent import ComicPlan
from app.services.agent_hitl import (
    AgentApprovalError,
    approved_comic_plan,
    create_comic_plan_artifact,
    decide_approval,
    emit_agent_event,
)


def make_plan(style_id: str, panel_count: int, suffix: str = "") -> ComicPlan:
    return ComicPlan.model_validate(
        {
            "schema_version": 1,
            "title": f"测试漫画{suffix}",
            "story_summary": f"连续推进的测试故事{suffix}",
            "aspect_ratio": "3:4",
            "style_ref_id": style_id,
            "panels": [
                {
                    "panel_key": f"panel-{index}",
                    "story_beat": f"剧情推进 {index}{suffix}",
                    "visual_goal": f"画面目标 {index}",
                    "required_text": [],
                    "image_prompt": f"最终单图指令 {index}",
                }
                for index in range(1, panel_count + 1)
            ],
            "estimated_image_credits": panel_count,
        }
    )


class AgentHitlEventStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        with self.Session() as db:
            user = User(email="hitl@example.com", password_hash="hash")
            conversation = AgentConversation(owner=user, title="HITL")
            run = AgentRun(conversation=conversation, turn_id="turn-1")
            db.add_all([user, conversation, run])
            db.commit()
            self.user_id = user.id
            self.run_id = run.id
            self.style_id = "a" * 32

    def test_comic_plan_accepts_2_6_8_and_rejects_bounds_or_discontinuous_keys(self) -> None:
        for count in (2, 6, 8):
            with self.subTest(count=count):
                self.assertEqual(count, len(make_plan(self.style_id, count).panels))
        for count in (1, 9):
            payload = make_plan(self.style_id, 2).model_dump()
            payload["panels"] = [
                {
                    "panel_key": f"panel-{index}",
                    "story_beat": f"剧情 {index}",
                    "visual_goal": "画面",
                    "required_text": [],
                    "image_prompt": "指令",
                }
                for index in range(1, count + 1)
            ]
            payload["estimated_image_credits"] = count
            with self.assertRaises(ValidationError):
                ComicPlan.model_validate(payload)
        payload = make_plan(self.style_id, 2).model_dump()
        payload["panels"][1]["panel_key"] = "panel-3"
        with self.assertRaises(ValidationError):
            ComicPlan.model_validate(payload)

    def test_approval_is_hash_bound_idempotent_and_changes_create_new_version(self) -> None:
        with self.Session() as db:
            run = db.get(AgentRun, self.run_id)
            first, approval = create_comic_plan_artifact(
                db,
                run=run,
                plan=make_plan(self.style_id, 2),
            )
            self.assertEqual(AgentRunStatus.waiting_for_input, run.status)
            decide_approval(
                db,
                approval=approval,
                user_id=self.user_id,
                decision="request_changes",
                feedback="结尾改得更坚定",
            )
            repeated = decide_approval(
                db,
                approval=approval,
                user_id=self.user_id,
                decision="request_changes",
                feedback="结尾改得更坚定",
            )
            self.assertEqual(AgentApprovalStatus.changes_requested, repeated.status)
            second, second_approval = create_comic_plan_artifact(
                db,
                run=run,
                plan=make_plan(self.style_id, 2, "新版"),
            )
            self.assertEqual(2, second.version)
            self.assertEqual(AgentArtifactStatus.superseded, first.status)
            decide_approval(
                db,
                approval=second_approval,
                user_id=self.user_id,
                decision="approve",
                feedback=None,
            )
            self.assertIsNotNone(approved_comic_plan(db, run))
            second.content_json = second.content_json.replace("新版", "被篡改", 1)
            db.commit()
            with self.assertRaises(AgentApprovalError):
                approved_comic_plan(db, run)

    def test_events_have_run_local_monotonic_sequence_and_deduplicate_checkpoint(self) -> None:
        with self.Session() as db:
            run = db.get(AgentRun, self.run_id)
            first = emit_agent_event(
                db,
                run=run,
                event_type=AgentEventType.run_started,
                payload={"status": "running"},
                deduplicate=True,
            )
            repeated = emit_agent_event(
                db,
                run=run,
                event_type=AgentEventType.run_started,
                payload={"status": "running"},
                deduplicate=True,
            )
            second = emit_agent_event(
                db,
                run=run,
                event_type=AgentEventType.skill_loaded,
                payload={"name": "idea-to-comic", "version": 1},
            )
            db.commit()
            events = db.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run.id)
                .order_by(AgentEvent.sequence)
            ).all()
        self.assertEqual(first.id, repeated.id)
        self.assertEqual([1, 2], [event.sequence for event in events])
        self.assertEqual(second.id, events[-1].id)


if __name__ == "__main__":
    unittest.main()
