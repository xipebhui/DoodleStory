import unittest

from datetime import timedelta

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    DurableAgentArtifact,
    DurableAgentPlanRevision,
    DurableAgentTask,
    DurableAgentWorkflow,
    NativeAgentConversation,
    NativeAgentArticleApproval,
    NativeAgentArtifact,
    NativeAgentRun,
    User,
)
from app.models.enums import AgentRunStatus, AgentSkillStatus
from app.schemas.native_agent import NativeAgentArtifactRead
from app.services.durable_agent_runtime import (
    claim_attempt,
    add_supplement_research_task,
    initialize_workflow,
    mirror_native_article_approval,
    open_gate,
    record_artifact,
    resolve_gate,
    recover_attempts,
)


class DurableAgentRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record) -> None:
            del record
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        self.user = User(email="durable@example.com", password_hash="hash")
        self.db.add(self.user)
        self.db.flush()
        skill = AgentSkill(
            slug="article-creation-team",
            name="文案创作团队",
            description="test",
            draft_instructions="test",
            draft_tool_names_json='["write_article","review_article"]',
            draft_revision=1,
            status=AgentSkillStatus.published,
        )
        self.db.add(skill)
        self.db.flush()
        version = AgentSkillVersion(
            skill_id=skill.id,
            version=1,
            name_snapshot=skill.name,
            description_snapshot=skill.description,
            instructions=skill.draft_instructions,
            tool_names_json=skill.draft_tool_names_json,
            content_hash="sha256:skill",
        )
        self.db.add(version)
        self.db.flush()
        skill.active_version_id = version.id
        conversation = NativeAgentConversation(
            owner_user_id=self.user.id,
            title="Durable test",
        )
        self.db.add(conversation)
        self.db.flush()
        self.run = NativeAgentRun(
            conversation_id=conversation.id,
            skill_version_id=version.id,
            status=AgentRunStatus.queued,
            model_snapshot="test",
            skill_name_snapshot=version.name_snapshot,
            skill_version_snapshot=version.version,
            skill_content_hash_snapshot=version.content_hash,
            style_reference_urls_json="[]",
        )
        self.db.add(self.run)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_topic_approval_releases_draft_without_finishing_workflow(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        topic_task = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "research_topics",
            )
        )
        self.assertIsNotNone(topic_task)
        attempt = claim_attempt(
            self.db,
            attempt_id=topic_task.current_attempt_id,
            worker_id="test-worker",
        )
        self.assertIsNotNone(attempt)
        artifact = record_artifact(
            self.db,
            workflow=workflow,
            task_key="research_topics",
            artifact_type="topic_candidates",
            content={"candidates": [{"id": "topic-1", "title": "第一个选题"}]},
        )
        gate = open_gate(
            self.db,
            workflow=workflow,
            task_key="topic_selection_gate",
            artifact=artifact,
            purpose="topic_selection",
            on_approve_action="advance_to_draft",
        )
        self.db.commit()

        attempts = resolve_gate(
            self.db,
            gate=gate,
            user=self.user,
            decision="approve",
            feedback="使用第一个选题就可以",
        )
        self.db.commit()

        self.assertEqual("queued", workflow.status)
        self.assertNotEqual("succeeded", workflow.status)
        self.assertEqual(1, len(attempts))
        draft_task = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "write_draft",
            )
        )
        self.assertEqual("ready", draft_task.status)
        self.assertEqual(draft_task.id, attempts[0].task_id)
        self.assertEqual("topic_candidates", artifact.artifact_type)

    def test_native_run_has_one_durable_workflow(self) -> None:
        first = initialize_workflow(self.db, native_run=self.run)
        replay = initialize_workflow(self.db, native_run=self.run)
        self.db.commit()
        self.assertEqual(first.id, replay.id)
        self.assertEqual(
            1,
            len(
                self.db.scalars(
                    select(DurableAgentWorkflow).where(
                        DurableAgentWorkflow.native_run_id == self.run.id
                    )
                ).all()
            ),
        )

    def test_recovery_skips_gate_and_resumes_expired_attempt(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        topic_task = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "research_topics",
            )
        )
        attempt = claim_attempt(
            self.db,
            attempt_id=topic_task.current_attempt_id,
            worker_id="test-worker",
        )
        attempt.lease_expires_at = attempt.started_at - timedelta(seconds=1)
        self.db.commit()

        recovered = recover_attempts(self.db)
        self.db.commit()
        self.assertEqual(1, len(recovered))
        self.assertEqual("interrupted", attempt.status)
        replacement = self.db.get(type(attempt), recovered[0])
        self.assertEqual("resume", replacement.attempt_kind)

    def test_legacy_candidate_approval_maps_to_topic_gate(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        native_artifact = NativeAgentArtifact(
            run_id=self.run.id,
            artifact_type="final_article",
            schema_version=1,
            version=1,
            status="awaiting_approval",
            producer_role="director",
            content_json='{"title":"候选选题","body_markdown":"topic_candidates：第一个选题"}',
            content_hash="sha256:legacy-topic",
        )
        self.db.add(native_artifact)
        self.db.flush()
        native_approval = NativeAgentArticleApproval(
            run_id=self.run.id,
            artifact_id=native_artifact.id,
            artifact_hash=native_artifact.content_hash,
            status="pending",
        )
        self.db.add(native_approval)
        self.db.commit()

        gate = mirror_native_article_approval(
            self.db,
            native_run=self.run,
            native_approval=native_approval,
        )
        attempts = resolve_gate(
            self.db,
            gate=gate,
            user=self.user,
            decision="approve",
            feedback="使用第一个选题就可以",
        )
        self.db.commit()

        self.assertEqual(workflow.id, gate.workflow_id)
        self.assertEqual("topic_selection", gate.purpose)
        self.assertEqual("advance_to_draft", gate.on_approve_action)
        self.assertEqual(1, len(attempts))
        draft_task = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "write_draft",
            )
        )
        self.assertEqual(draft_task.id, attempts[0].task_id)

    def test_plan_revisions_are_append_only_after_gate_decisions(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        topic_task = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "research_topics",
            )
        )
        claim_attempt(
            self.db,
            attempt_id=topic_task.current_attempt_id,
            worker_id="test-worker",
        )
        artifact = record_artifact(
            self.db,
            workflow=workflow,
            task_key="research_topics",
            artifact_type="topic_candidates",
            content={"candidates": [{"id": "topic-1"}]},
        )
        gate = open_gate(
            self.db,
            workflow=workflow,
            task_key="topic_selection_gate",
            artifact=artifact,
            purpose="topic_selection",
            on_approve_action="advance_to_draft",
        )
        resolve_gate(
            self.db,
            gate=gate,
            user=self.user,
            decision="approve",
            feedback="使用第一个选题",
        )
        self.db.commit()
        revisions = self.db.scalars(
            select(DurableAgentPlanRevision)
            .where(DurableAgentPlanRevision.workflow_id == workflow.id)
            .order_by(DurableAgentPlanRevision.revision)
        ).all()
        self.assertEqual(
            [
                "initial task plan",
                "research_topics completed",
                "topic_selection gate opened",
                "topic_selection approved",
            ],
            [item.reason for item in revisions],
        )
        self.assertEqual(
            "write_draft",
            next(
                entry["task_key"]
                for entry in __import__("json").loads(revisions[-1].plan_json)
                if entry["status"] == "ready"
            ),
        )

    def test_supplement_research_can_only_be_added_once(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        topic_task = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "topic_selection_gate",
            )
        )
        topic_task.status = "succeeded"
        attempt = add_supplement_research_task(
            self.db,
            workflow=workflow,
            reason="Review 要求补充研究",
        )
        self.assertEqual("initial", attempt.attempt_kind)
        with self.assertRaises(RuntimeError):
            add_supplement_research_task(
                self.db,
                workflow=workflow,
                reason="重复补充研究",
            )

    def test_review_requesting_supplement_research_only_prepares_research(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        tasks = {
            task.task_key: task
            for task in self.db.scalars(
                select(DurableAgentTask).where(
                    DurableAgentTask.workflow_id == workflow.id
                )
            ).all()
        }
        tasks["topic_selection_gate"].status = "succeeded"
        tasks["write_draft"].status = "succeeded"
        tasks["draft_review_gate"].status = "succeeded"
        tasks["review_draft"].status = "succeeded"
        artifact = DurableAgentArtifact(
            workflow_id=workflow.id,
            task_id=tasks["review_draft"].id,
            artifact_key="article_review",
            artifact_type="article_review",
            version=1,
            content_json='{"verdict":"changes_required"}',
            content_hash="sha256:review",
        )
        self.db.add(artifact)
        self.db.flush()
        gate = open_gate(
            self.db,
            workflow=workflow,
            task_key="editorial_review_gate",
            artifact=artifact,
            purpose="editorial_review",
            on_approve_action="finish_run",
        )
        attempts = resolve_gate(
            self.db,
            gate=gate,
            user=self.user,
            decision="changes_requested",
            feedback="请先补充研究，再修改正文",
        )
        self.assertEqual(1, len(attempts))
        supplement = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "supplement_research",
            )
        )
        self.assertEqual(supplement.id, attempts[0].task_id)
        self.assertEqual("ready", supplement.status)
        self.assertEqual("succeeded", tasks["write_draft"].status)

    def test_topic_candidate_artifact_is_readable_by_legacy_api_schema(self) -> None:
        artifact = NativeAgentArtifactRead(
            id="topic-artifact",
            artifact_type="topic_candidates",
            schema_version=1,
            version=1,
            status="awaiting_approval",
            producer_role="writer",
            content={"candidates": ["A", "B", "C"]},
            content_hash="sha256:topic",
            approval=None,
            created_at=self.run.created_at,
            updated_at=self.run.updated_at,
        )
        self.assertEqual("topic_candidates", artifact.artifact_type)


if __name__ == "__main__":
    unittest.main()
