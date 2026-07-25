import json
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.agent_conversations import (
    create_agent_message,
    list_agent_character_resources,
    list_agent_panel_image_resources,
    list_agent_skill_resources,
    list_agent_style_resources,
    list_agent_task_panel_resources,
    list_agent_task_resources,
)
from app.core.database import Base
from app.models.entities import (
    AgentConversation,
    AgentMessage,
    AgentRun,
    AgentSkill,
    AgentSkillVersion,
    FileAsset,
    GeneratedImage,
    GenerationTask,
    Style,
    TaskPanel,
    User,
    UserCharacter,
)
from app.models.enums import (
    AgentMessageRole,
    AgentSkillStatus,
    FileAssetPurpose,
    GeneratedImageStatus,
    ImageCountMode,
    StorageBackend,
    StoryInputMode,
    StyleStatus,
    TaskStatus,
)
from app.schemas.agent import AgentMessageCreate, AgentResourceKind, AgentResourceRef
from app.services.agent_resources import (
    AgentResourceResolutionError,
    AgentResourceResolver,
    AgentResourceRoute,
)
from app.services.agent_runner import build_agent_input


class AgentResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.owner = User(email="resource-owner@example.com", password_hash="hash")
        self.other = User(email="resource-other@example.com", password_hash="hash")
        self.db.add_all([self.owner, self.other])
        self.db.flush()
        self.style = Style(
            name="真实水彩",
            status=StyleStatus.active,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_prompt="清透水彩",
        )
        self.disabled_style = Style(
            name="停用风格",
            status=StyleStatus.disabled,
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
            style_prompt="停用",
        )
        self.db.add_all([self.style, self.disabled_style])
        self.db.flush()
        self.character = self._character(self.owner, "林夏")
        self.other_character = self._character(self.other, "越权角色")
        self.task = self._task(self.owner, "街角画画")
        self.other_task = self._task(self.other, "其他人的故事")
        self.db.flush()
        self.panel = TaskPanel(
            task_id=self.task.id,
            panel_order=1,
            original_text_segment="林夏在街角画画",
            text_layout="克制而安静",
        )
        self.other_panel = TaskPanel(
            task_id=self.other_task.id,
            panel_order=1,
            original_text_segment="不可见 Panel",
        )
        self.db.add_all([self.panel, self.other_panel])
        self.db.flush()
        self.image = GeneratedImage(
            task_id=self.task.id,
            panel_id=self.panel.id,
            owner_user_id=self.owner.id,
            status=GeneratedImageStatus.queued,
            generation_number=2,
            is_current=True,
            image_model_name_snapshot="gpt-image-2",
        )
        self.other_image = GeneratedImage(
            task_id=self.other_task.id,
            panel_id=self.other_panel.id,
            owner_user_id=self.other.id,
            status=GeneratedImageStatus.queued,
            generation_number=1,
            image_model_name_snapshot="gpt-image-2",
        )
        self.db.add_all([self.image, self.other_image])
        self.skill = AgentSkill(
            owner_user_id=self.owner.id,
            slug="story-review",
            name="故事检查",
            description="检查故事结构时使用",
            draft_instructions="# 目标\n检查故事。\n# 方法\n给出明确问题。",
            draft_tool_names_json="[]",
            draft_revision=1,
            status=AgentSkillStatus.published,
        )
        self.other_skill = AgentSkill(
            owner_user_id=self.other.id,
            slug="private-skill",
            name="越权 Skill",
            description="不应可见",
            draft_instructions="不可见",
            draft_tool_names_json="[]",
            draft_revision=1,
            status=AgentSkillStatus.published,
        )
        self.db.add_all([self.skill, self.other_skill])
        self.db.flush()
        self.skill_version = AgentSkillVersion(
            skill_id=self.skill.id,
            version=1,
            name_snapshot=self.skill.name,
            description_snapshot=self.skill.description,
            instructions=self.skill.draft_instructions,
            tool_names_json="[]",
            content_hash="sha256:story-review",
            published_by_user_id=self.owner.id,
        )
        self.other_skill_version = AgentSkillVersion(
            skill_id=self.other_skill.id,
            version=1,
            name_snapshot=self.other_skill.name,
            description_snapshot=self.other_skill.description,
            instructions=self.other_skill.draft_instructions,
            tool_names_json="[]",
            content_hash="sha256:private-skill",
            published_by_user_id=self.other.id,
        )
        self.db.add_all([self.skill_version, self.other_skill_version])
        self.db.flush()
        self.skill.active_version_id = self.skill_version.id
        self.other_skill.active_version_id = self.other_skill_version.id
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def _asset(self, suffix: str) -> FileAsset:
        asset = FileAsset(
            purpose=FileAssetPurpose.character_reference,
            storage_backend=StorageBackend.local,
            storage_key=f"agent-resource/{suffix}.png",
            content_type="image/png",
            byte_size=100,
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def _character(self, owner: User, name: str) -> UserCharacter:
        asset = self._asset(name)
        character = UserCharacter(
            owner_user_id=owner.id,
            name=name,
            description=f"{name} 的固定外观",
            reference_asset_id=asset.id,
        )
        self.db.add(character)
        self.db.flush()
        return character

    def _task(self, owner: User, title: str) -> GenerationTask:
        task = GenerationTask(
            owner_user_id=owner.id,
            display_title=title,
            original_text="真实故事",
            story_input_mode=StoryInputMode.adapted,
            image_count_mode=ImageCountMode.fixed,
            requested_image_count=1,
            style_id=self.style.id,
            style_name_snapshot=self.style.name,
            style_prompt_snapshot=self.style.style_prompt,
            image_model_name_snapshot=self.style.image_model_name,
            style_aspect_ratio_snapshot=self.style.aspect_ratio,
            status=TaskStatus.succeeded,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def test_resolver_canonicalizes_full_parent_chain_and_safe_context(self) -> None:
        resolved = AgentResourceResolver().resolve(
            self.db,
            owner_user_id=self.owner.id,
            refs=[
                AgentResourceRef(
                    kind=AgentResourceKind.task,
                    id=self.task.id,
                    display_name="伪造任务名",
                ),
                AgentResourceRef(kind=AgentResourceKind.panel, id=self.panel.id),
                AgentResourceRef(
                    kind=AgentResourceKind.image_version,
                    id=self.image.id,
                ),
            ],
        )

        self.assertEqual(AgentResourceRoute.continue_task, resolved.route)
        self.assertEqual("街角画画", resolved.refs[0].display_name)
        self.assertEqual("Panel 1", resolved.refs[1].display_name)
        self.assertEqual("Panel 1 · v2", resolved.refs[2].display_name)
        self.assertEqual(self.panel.id, resolved.model_context["image_version"]["panel_id"])
        self.assertNotIn("owner_user_id", str(resolved.model_context))
        self.assertNotIn("storage_key", str(resolved.model_context))

    def test_resolver_rejects_cross_owner_inactive_and_wrong_parent_resources(self) -> None:
        rejected = [
            [AgentResourceRef(kind=AgentResourceKind.style, id=self.disabled_style.id)],
            [AgentResourceRef(kind=AgentResourceKind.character, id=self.other_character.id)],
            [AgentResourceRef(kind=AgentResourceKind.task, id=self.other_task.id)],
            [
                AgentResourceRef(kind=AgentResourceKind.task, id=self.task.id),
                AgentResourceRef(kind=AgentResourceKind.panel, id=self.other_panel.id),
            ],
            [
                AgentResourceRef(kind=AgentResourceKind.task, id=self.task.id),
                AgentResourceRef(kind=AgentResourceKind.panel, id=self.panel.id),
                AgentResourceRef(kind=AgentResourceKind.image_version, id=self.other_image.id),
            ],
        ]
        for refs in rejected:
            with self.subTest(refs=refs), self.assertRaises(AgentResourceResolutionError):
                AgentResourceResolver().resolve(
                    self.db,
                    owner_user_id=self.owner.id,
                    refs=refs,
                )

    def test_combination_matrix_routes_and_rejects_ambiguous_refs(self) -> None:
        created = AgentResourceResolver().resolve(
            self.db,
            owner_user_id=self.owner.id,
            refs=[
                AgentResourceRef(kind=AgentResourceKind.style, id=self.style.id),
                AgentResourceRef(kind=AgentResourceKind.character, id=self.character.id),
            ],
        )
        discussion = AgentResourceResolver().resolve(
            self.db,
            owner_user_id=self.owner.id,
            refs=[],
        )
        self.assertEqual(AgentResourceRoute.create_comic, created.route)
        self.assertEqual(AgentResourceRoute.discussion, discussion.route)
        with self.assertRaises(AgentResourceResolutionError):
            AgentResourceResolver().resolve(
                self.db,
                owner_user_id=self.owner.id,
                refs=[AgentResourceRef(kind=AgentResourceKind.panel, id=self.panel.id)],
            )
        with self.assertRaises(AgentResourceResolutionError):
            AgentResourceResolver().resolve(
                self.db,
                owner_user_id=self.owner.id,
                refs=[
                    AgentResourceRef(kind=AgentResourceKind.task, id=self.task.id),
                    AgentResourceRef(kind=AgentResourceKind.task, id=self.other_task.id),
                ],
            )
        with self.assertRaises(AgentResourceResolutionError):
            AgentResourceResolver().resolve(
                self.db,
                owner_user_id=self.owner.id,
                refs=[
                    AgentResourceRef(kind=AgentResourceKind.skill, id=self.skill_version.id),
                    AgentResourceRef(kind=AgentResourceKind.skill, id=self.skill_version.id),
                ],
            )

    def test_skill_ref_uses_exact_active_version_and_server_safe_snapshot(self) -> None:
        resolved = AgentResourceResolver().resolve(
            self.db,
            owner_user_id=self.owner.id,
            refs=[
                AgentResourceRef(
                    kind=AgentResourceKind.skill,
                    id=self.skill_version.id,
                    display_name="伪造名称",
                    safe_summary={"instructions": "伪造正文"},
                ),
                AgentResourceRef(kind=AgentResourceKind.style, id=self.style.id),
            ],
        )

        self.assertEqual(self.skill_version.id, resolved.skill_version.id)
        self.assertEqual("故事检查 · v1", resolved.refs[0].display_name)
        self.assertEqual(self.skill.id, resolved.refs[0].safe_summary["skill_id"])
        self.assertEqual([], resolved.refs[0].safe_summary["tool_names"])
        self.assertNotIn("instructions", resolved.refs[0].safe_summary)
        with self.assertRaises(AgentResourceResolutionError):
            AgentResourceResolver().resolve(
                self.db,
                owner_user_id=self.owner.id,
                refs=[
                    AgentResourceRef(
                        kind=AgentResourceKind.skill,
                        id=self.other_skill_version.id,
                    )
                ],
            )

    def test_message_acceptance_canonicalizes_skill_and_pins_same_version_on_run(self) -> None:
        conversation = AgentConversation(owner_user_id=self.owner.id, title="Skill 引用")
        self.db.add(conversation)
        self.db.commit()
        with patch(
            "app.api.agent_conversations.enqueue_agent_run",
            new=AsyncMock(),
        ):
            accepted = asyncio.run(
                create_agent_message(
                    conversation.id,
                    AgentMessageCreate(
                        content="请检查这个故事",
                        resource_refs=[
                            AgentResourceRef(
                                kind=AgentResourceKind.skill,
                                id=self.skill_version.id,
                                display_name="伪造名称",
                            )
                        ],
                    ),
                    user=self.owner,
                    db=self.db,
                )
            )

        run = self.db.get(AgentRun, accepted.data.run.id)
        saved_ref = accepted.data.message.resource_refs[0]
        self.assertEqual(self.skill_version.id, run.skill_version_id)
        self.assertEqual("故事检查 · v1", saved_ref.display_name)
        self.assertEqual("sha256:story-review", saved_ref.safe_summary["content_hash"])

        self.skill.status = AgentSkillStatus.archived
        self.db.commit()
        with self.assertRaises(AgentResourceResolutionError):
            AgentResourceResolver().resolve(
                self.db,
                owner_user_id=self.owner.id,
                refs=[
                    AgentResourceRef(
                        kind=AgentResourceKind.skill,
                        id=self.skill_version.id,
                    )
                ],
            )

    def test_resource_queries_are_owner_scoped_searchable_bounded_summaries(self) -> None:
        styles = list_agent_style_resources(
            query="水彩",
            limit=1,
            user=self.owner,
            db=self.db,
        )
        characters = list_agent_character_resources(
            query="林",
            limit=20,
            user=self.owner,
            db=self.db,
        )
        tasks = list_agent_task_resources(
            query="街角",
            limit=20,
            user=self.owner,
            db=self.db,
        )
        skills = list_agent_skill_resources(
            query="故事",
            limit=20,
            user=self.owner,
            db=self.db,
        )
        panels = list_agent_task_panel_resources(
            self.task.id,
            user=self.owner,
            db=self.db,
        )
        images = list_agent_panel_image_resources(
            self.panel.id,
            user=self.owner,
            db=self.db,
            limit=20,
        )

        self.assertEqual(["真实水彩"], [item.display_name for item in styles.items])
        self.assertEqual(["林夏"], [item.display_name for item in characters.items])
        self.assertEqual(["街角画画"], [item.display_name for item in tasks.items])
        self.assertEqual(self.skill_version.id, skills.items[0].id)
        self.assertEqual(self.skill.id, skills.items[0].parent_id)
        self.assertEqual(self.task.id, panels.items[0].parent_id)
        self.assertEqual(self.panel.id, images.items[0].parent_id)
        self.assertFalse(hasattr(tasks.items[0], "original_text"))

    def test_build_agent_input_replays_saved_safe_snapshot(self) -> None:
        resolved = AgentResourceResolver().resolve(
            self.db,
            owner_user_id=self.owner.id,
            refs=[
                AgentResourceRef(kind=AgentResourceKind.task, id=self.task.id),
                AgentResourceRef(kind=AgentResourceKind.panel, id=self.panel.id),
            ],
        )
        conversation = AgentConversation(owner_user_id=self.owner.id, title="重放")
        self.db.add(conversation)
        self.db.flush()
        message = AgentMessage(
            conversation_id=conversation.id,
            turn_id="turn-resource-replay",
            role=AgentMessageRole.user,
            content="这一格发生了什么？",
            resource_refs_json=json.dumps(
                [ref.model_dump(mode="json") for ref in resolved.refs],
                ensure_ascii=False,
            ),
            sequence=1,
        )
        run = AgentRun(
            conversation_id=conversation.id,
            turn_id=message.turn_id,
        )
        self.db.add_all([message, run])
        self.db.commit()

        replay = build_agent_input(self.db, run)

        self.assertIn('"resource_context"', replay[0]["content"])
        self.assertIn(self.panel.id, replay[0]["content"])
        self.assertIn("林夏在街角画画", replay[0]["content"])


if __name__ == "__main__":
    unittest.main()
