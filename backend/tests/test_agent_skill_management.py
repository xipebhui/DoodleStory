from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import AgentRun, AgentSkill, AgentSkillVersion, User
from app.models.enums import AgentSkillStatus
from app.services.agent_skill_management import (
    AgentSkillConflictError,
    AgentSkillNotFoundError,
    activate_skill_version,
    archive_skill,
    clone_skill_version,
    create_skill,
    delete_unpublished_skill,
    list_skills,
    load_owned_skill,
    publish_skill,
    restore_skill,
    selectable_tool_catalog,
    seed_system_skills,
    update_skill_draft,
)


SKILL_TEXT = """# 目标
把用户的生活观察整理为一组可执行的内容。

# 方法
先理解目标和已有资源，再形成方案；涉及生成图片时先请求用户确认。

# 完成条件
真实 Tool 返回成功后汇报结果。
"""


def write_system_skill(root: Path) -> None:
    skill_dir = root / "idea-to-comic"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: idea-to-comic
description: 当用户希望把想法创作为连续漫画时使用。
version: 2
---

# 目标
把用户想法创作为连续漫画。

# 方法
形成方案并请求确认，再调用允许的图片 Tool。
""",
        encoding="utf-8",
    )


class AgentSkillManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        self.owner = User(email="skill-owner@example.com", password_hash="hash")
        self.other = User(email="skill-other@example.com", password_hash="hash")
        self.db.add_all([self.owner, self.other])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_selectable_tool_catalog_includes_native_speech_tool(self) -> None:
        tools = {
            str(item["name"]): item
            for item in selectable_tool_catalog()
        }

        self.assertIn("generate_speech", tools)
        self.assertEqual("生成语音", tools["generate_speech"]["display_name"])
        self.assertTrue(tools["generate_speech"]["has_side_effects"])
        self.assertTrue(tools["generate_speech"]["may_wait"])
        self.assertIn("render_story_video", tools)
        self.assertEqual(
            "渲染故事视频",
            tools["render_story_video"]["display_name"],
        )
        self.assertTrue(tools["render_story_video"]["has_side_effects"])
        self.assertTrue(tools["render_story_video"]["may_wait"])
        self.assertIn("capture_wechat_article", tools)
        self.assertEqual(
            "微信公众号文章",
            tools["capture_wechat_article"]["display_name"],
        )
        self.assertIn(
            "微信公众号",
            tools["capture_wechat_article"]["description"],
        )
        self.assertTrue(tools["capture_wechat_article"]["has_side_effects"])
        self.assertTrue(tools["capture_wechat_article"]["may_wait"])
        self.assertIn("inspect_youtube_channel", tools)
        self.assertEqual(
            "读取 YouTube 频道",
            tools["inspect_youtube_channel"]["display_name"],
        )
        self.assertTrue(tools["inspect_youtube_channel"]["has_side_effects"])
        self.assertTrue(tools["inspect_youtube_channel"]["may_wait"])

    def create_draft(self, *, owner: User | None = None) -> AgentSkill:
        return create_skill(
            self.db,
            user=owner or self.owner,
            name="四格反转",
            description="当用户希望把生活观察创作为四格反转内容时使用。",
            instructions=SKILL_TEXT,
            tool_names=["inspect_image", "generate_image"],
        )

    def test_create_update_and_owner_scoped_list(self) -> None:
        skill = self.create_draft()
        self.create_draft(owner=self.other)

        self.assertEqual(["generate_image", "inspect_image"], skill.draft_tool_names)
        page = list_skills(
            self.db,
            user_id=self.owner.id,
            scope="mine",
            status=None,
            query="反转",
            page=1,
            page_size=20,
        )
        self.assertEqual(1, page.total)
        updated = update_skill_draft(
            self.db,
            skill=skill,
            expected_draft_revision=1,
            name="三格反转",
            description="当用户希望创作三格反转图片故事时使用。",
            instructions=SKILL_TEXT + "\n补充检查角色连续性。",
            tool_names=["inspect_image"],
        )
        self.assertEqual(2, updated.draft_revision)
        self.assertEqual("三格反转", updated.name)

        with self.assertRaises(AgentSkillConflictError):
            update_skill_draft(
                self.db,
                skill=updated,
                expected_draft_revision=1,
                name=updated.name,
                description=updated.description,
                instructions=updated.draft_instructions,
                tool_names=["inspect_image"],
            )
        with self.assertRaises(AgentSkillNotFoundError):
            load_owned_skill(
                self.db,
                skill_id=skill.id,
                user_id=self.other.id,
            )

    def test_publish_is_immutable_idempotent_and_old_version_can_activate(self) -> None:
        skill = self.create_draft()
        first = publish_skill(
            self.db,
            skill=skill,
            user=self.owner,
            expected_draft_revision=1,
            idempotency_key="publish-first-0001",
        )
        replayed = publish_skill(
            self.db,
            skill=skill,
            user=self.owner,
            expected_draft_revision=999,
            idempotency_key="publish-first-0001",
        )
        self.assertEqual(first.id, replayed.id)
        self.assertEqual(1, first.version)
        original_instructions = first.instructions

        update_skill_draft(
            self.db,
            skill=skill,
            expected_draft_revision=1,
            name=skill.name,
            description=skill.description,
            instructions=SKILL_TEXT + "\n新版本先检查画面文字准确性。",
            tool_names=["generate_image", "inspect_image"],
        )
        second = publish_skill(
            self.db,
            skill=skill,
            user=self.owner,
            expected_draft_revision=2,
            idempotency_key="publish-second-0002",
        )
        self.db.refresh(first)
        self.assertEqual(2, second.version)
        self.assertEqual(original_instructions, first.instructions)
        self.assertNotEqual(first.content_hash, second.content_hash)
        self.assertEqual(second.id, skill.active_version_id)

        activate_skill_version(self.db, skill=skill, version=first)
        self.assertEqual(first.id, skill.active_version_id)
        self.assertEqual(2, self.db.scalar(select(func.count(AgentSkillVersion.id))))

    def test_archive_restore_delete_and_clone_semantics(self) -> None:
        draft = self.create_draft()
        delete_unpublished_skill(self.db, skill=draft)
        self.assertIsNone(self.db.get(AgentSkill, draft.id))

        source = self.create_draft()
        version = publish_skill(
            self.db,
            skill=source,
            user=self.owner,
            expected_draft_revision=1,
            idempotency_key="published-cannot-delete",
        )
        with self.assertRaises(AgentSkillConflictError):
            delete_unpublished_skill(self.db, skill=source)
        archive_skill(self.db, skill=source)
        self.assertEqual(AgentSkillStatus.archived, source.status)
        restored = restore_skill(self.db, skill=source)
        self.assertEqual(AgentSkillStatus.published, restored.status)

        cloned = clone_skill_version(
            self.db,
            source_skill=source,
            source_version=version,
            user=self.other,
        )
        self.assertEqual(AgentSkillStatus.draft, cloned.status)
        self.assertIsNone(cloned.active_version_id)
        self.assertEqual(self.other.id, cloned.owner_user_id)
        self.assertEqual(
            0,
            self.db.scalar(
                select(func.count(AgentSkillVersion.id)).where(
                    AgentSkillVersion.skill_id == cloned.id
                )
            ),
        )

    def test_system_seed_is_idempotent_and_system_slug_is_unique(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            write_system_skill(root)
            first = seed_system_skills(self.db, skill_root=root)
            second = seed_system_skills(self.db, skill_root=root)
        self.assertEqual(first.id, second.id)
        self.assertIsNone(first.owner_user_id)
        self.assertEqual(AgentSkillStatus.published, first.status)
        self.assertIsNotNone(first.active_version_id)
        self.assertNotIn("---", first.draft_instructions)

        duplicate = AgentSkill(
            owner_user_id=None,
            slug="idea-to-comic",
            name="重复系统 Skill",
            description="不应写入",
            draft_instructions=SKILL_TEXT,
            draft_tool_names_json="[]",
            draft_revision=1,
            status=AgentSkillStatus.draft,
        )
        self.db.add(duplicate)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_run_pinned_version_survives_active_switch_and_archive(self) -> None:
        skill = self.create_draft()
        first = publish_skill(
            self.db,
            skill=skill,
            user=self.owner,
            expected_draft_revision=1,
            idempotency_key="pin-version-first",
        )
        from app.models.entities import AgentConversation

        conversation = AgentConversation(owner=self.owner, title="Pinned")
        run = AgentRun(
            conversation=conversation,
            turn_id="pin-turn",
            skill_version_id=first.id,
        )
        self.db.add_all([conversation, run])
        self.db.commit()

        update_skill_draft(
            self.db,
            skill=skill,
            expected_draft_revision=1,
            name=skill.name,
            description=skill.description,
            instructions=SKILL_TEXT + "\n发布第二版。",
            tool_names=["generate_image"],
        )
        second = publish_skill(
            self.db,
            skill=skill,
            user=self.owner,
            expected_draft_revision=2,
            idempotency_key="pin-version-second",
        )
        archive_skill(self.db, skill=skill)
        self.db.refresh(run)
        self.assertEqual(first.id, run.skill_version_id)
        self.assertNotEqual(second.id, run.skill_version_id)
