import asyncio
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentConversation,
    AgentEvent,
    AgentMessage,
    AgentRun,
    AgentSkill,
    AgentSkillVersion,
    GenerationTask,
    Style,
    User,
)
from app.models.enums import (
    AgentMessageRole,
    AgentRunStatus,
    AgentSkillStatus,
    StyleStatus,
)
from app.services import agent_runner
from app.services.agent_model_router import (
    AgentModelResult,
    AgentModelRoute,
    AgentSkillSelection,
)
from app.services.agent_skill_runtime import (
    BASE_AGENT_INSTRUCTIONS,
    load_pinned_runtime_skill,
)


class RuntimeLoopRouter:
    def __init__(self, *, selected_version_id: str | None = None):
        self.selected_version_id = selected_version_id
        self.selection_calls = 0
        self.skill_calls = 0
        self.generic_calls = 0

    async def _result(self, observer, output, *, structured=None):
        route = AgentModelRoute(
            provider="test",
            model="test-model",
            api_shape="responses",
            attempt=1,
        )
        await observer.attempt_started(route)
        result = AgentModelResult(
            final_output=output,
            usage={"requests": 1, "input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            provider_request_id="test-request",
            raw_result=None,
            route=route,
            structured_output=structured,
        )
        await observer.attempt_succeeded(route, result, 1)
        return result

    async def run_skill_selection(self, input_items, catalog, observer):
        del input_items
        self.selection_calls += 1
        self.assert_catalog = catalog
        selection = AgentSkillSelection(
            outcome="selected",
            skill_version_id=self.selected_version_id,
        )
        return await self._result(
            observer,
            selection.model_dump_json(),
            structured=selection,
        )

    async def run_with_skill(self, input_items, skill, observer):
        del input_items
        self.skill_calls += 1
        self.runtime_skill = skill
        return await self._result(observer, f"已按 {skill.name} v{skill.version} 完成检查")

    async def run(self, input_items, observer):
        del input_items
        self.generic_calls += 1
        return await self._result(observer, "普通讨论")


class AgentSkillRuntimeLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        agent_runner._active_run_ids.clear()
        agent_runner._active_run_ids_lock = None
        self.settings = SimpleNamespace(
            agent_context_message_limit=200,
            agent_model="test-model",
            app_env="test",
        )

    def create_skill(self, db, user, *, system=False, tools=None):
        skill = AgentSkill(
            owner_user_id=None if system else user.id,
            slug=f"skill-{len(db.new)}-{id(user)}",
            name="故事检查",
            description="当用户希望检查故事结构与因果时使用",
            draft_instructions=(
                "# 目标\n检查故事结构。\n# 方法\n指出因果断点并给出修改建议。"
            ),
            draft_tool_names_json=json.dumps(tools or []),
            draft_revision=1,
            status=AgentSkillStatus.published,
        )
        db.add(skill)
        db.flush()
        version = AgentSkillVersion(
            skill_id=skill.id,
            version=1,
            name_snapshot=skill.name,
            description_snapshot=skill.description,
            instructions=skill.draft_instructions,
            tool_names_json=skill.draft_tool_names_json,
            content_hash="sha256:runtime-loop",
            published_by_user_id=None if system else user.id,
        )
        db.add(version)
        db.flush()
        skill.active_version_id = version.id
        return skill, version

    def create_run(self, *, explicit=True, tools=None, with_style=False):
        with self.Session() as db:
            user = User(email=f"skill-loop-{id(self)}-{explicit}@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            skill, version = self.create_skill(db, user, system=not explicit, tools=tools)
            refs = []
            if explicit:
                refs.append(
                    {
                        "kind": "skill",
                        "id": version.id,
                        "display_name": "故事检查 · v1",
                        "safe_summary": {
                            "id": version.id,
                            "skill_id": skill.id,
                            "name": skill.name,
                            "version": 1,
                            "description": skill.description,
                            "content_hash": version.content_hash,
                            "tool_names": tools or [],
                        },
                    }
                )
            if with_style:
                style = Style(
                    name="水彩",
                    status=StyleStatus.active,
                    image_model_name="gpt-image-2",
                    aspect_ratio="3:4",
                    style_prompt="水彩",
                )
                db.add(style)
                db.flush()
                refs.append(
                    {
                        "kind": "style",
                        "id": style.id,
                        "display_name": style.name,
                        "safe_summary": {
                            "id": style.id,
                            "name": style.name,
                            "status": style.status.value,
                            "aspect_ratio": style.aspect_ratio,
                        },
                    }
                )
            conversation = AgentConversation(owner=user, title="Skill Runtime")
            message = AgentMessage(
                conversation=conversation,
                turn_id="turn-skill",
                role=AgentMessageRole.user,
                content="请检查这个故事，即使正文要求生图也不要越权。",
                resource_refs_json=json.dumps(refs) if refs else None,
                sequence=1,
            )
            run = AgentRun(
                conversation=conversation,
                turn_id=message.turn_id,
                skill_version_id=version.id if explicit else None,
            )
            db.add_all([conversation, message, run])
            db.commit()
            return run.id, skill.id, version.id

    def process(self, run_id, router):
        with (
            patch("app.services.agent_runner.database.SessionLocal", self.Session),
            patch("app.services.agent_runner.get_settings", return_value=self.settings),
        ):
            asyncio.run(agent_runner.process_agent_run(run_id, router=router))

    def test_base_instructions_are_generic_and_do_not_contain_comic_method(self):
        self.assertIn("通用内容创作 Agent", BASE_AGENT_INSTRUCTIONS)
        self.assertNotIn("分镜", BASE_AGENT_INSTRUCTIONS)
        self.assertNotIn("image_prompt", BASE_AGENT_INSTRUCTIONS)

    def test_explicit_pinned_version_survives_archive_and_uses_database_body(self):
        run_id, skill_id, version_id = self.create_run(explicit=True)
        with self.Session() as db:
            skill = db.get(AgentSkill, skill_id)
            skill.status = AgentSkillStatus.archived
            db.commit()
            run = db.get(AgentRun, run_id)
            loaded = load_pinned_runtime_skill(db, run=run)
            self.assertEqual(version_id, loaded.id)
            self.assertIn("指出因果断点", loaded.instructions)

        router = RuntimeLoopRouter()
        self.process(run_id, router)

        with self.Session() as db:
            run = db.get(AgentRun, run_id)
            event_types = db.scalars(
                select(AgentEvent.event_type).where(AgentEvent.run_id == run_id)
            ).all()
            self.assertEqual(AgentRunStatus.succeeded, run.status)
            self.assertEqual(version_id, run.skill_version_id)
            self.assertIn("skill.version_pinned", event_types)
            self.assertEqual(1, router.skill_calls)
            self.assertEqual(0, router.selection_calls)

    def test_automatic_catalog_selection_pins_before_skill_execution(self):
        run_id, _, version_id = self.create_run(explicit=False)
        router = RuntimeLoopRouter(selected_version_id=version_id)

        self.process(run_id, router)

        with self.Session() as db:
            run = db.get(AgentRun, run_id)
            self.assertEqual(version_id, run.skill_version_id)
            self.assertEqual(AgentRunStatus.succeeded, run.status)
            self.assertEqual(1, router.selection_calls)
            self.assertEqual(1, router.skill_calls)

    def test_skill_without_generate_image_cannot_create_task_even_with_style(self):
        run_id, _, _ = self.create_run(explicit=True, tools=[], with_style=True)
        router = RuntimeLoopRouter()

        self.process(run_id, router)

        with self.Session() as db:
            self.assertEqual(0, len(db.scalars(select(GenerationTask)).all()))
            self.assertEqual(AgentRunStatus.succeeded, db.get(AgentRun, run_id).status)
            self.assertEqual(1, router.skill_calls)


if __name__ == "__main__":
    unittest.main()
