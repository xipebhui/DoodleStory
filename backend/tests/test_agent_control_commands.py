import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    DurableAgentTask,
    DurableAgentToolEffect,
    NativeAgentConversation,
    NativeAgentRun,
    NativeAgentStep,
    User,
)
from app.models.enums import (
    AgentRunStatus,
    AgentSkillStatus,
    NativeAgentStepStatus,
    NativeAgentStepType,
)
from app.schemas.native_agent import DurableControlCommandCreate
from app.services.agent_control_commands import (
    AgentControlCommandError,
    durable_control_state,
    execute_durable_control_command,
)
from app.services.durable_agent_runtime import (
    initialize_workflow,
    open_gate,
    record_artifact,
)


class AgentControlCommandTests(unittest.TestCase):
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
        self.user = User(email="control@example.com", password_hash="hash")
        self.db.add(self.user)
        self.db.flush()
        skill = AgentSkill(
            slug="control-article",
            name="控制命令测试 Skill",
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
            content_hash="sha256:control-skill",
        )
        self.db.add(version)
        self.db.flush()
        skill.active_version_id = version.id
        conversation = NativeAgentConversation(
            owner_user_id=self.user.id,
            title="控制命令测试",
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
        self.db.flush()
        self.workflow = initialize_workflow(self.db, native_run=self.run)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_gate_command_is_idempotent_and_rejects_stale_revision(self) -> None:
        artifact = record_artifact(
            self.db,
            workflow=self.workflow,
            task_key="research_topics",
            artifact_type="topic_candidates",
            content={"candidates": [{"title": "测试选题"}]},
        )
        gate = open_gate(
            self.db,
            workflow=self.workflow,
            task_key="topic_selection_gate",
            artifact=artifact,
            purpose="topic_selection",
            on_approve_action="advance_to_draft",
        )
        self.db.commit()
        expected_version = self.workflow.state_version
        payload = DurableControlCommandCreate(
            command="approve_gate",
            idempotency_key="approve-topic-001",
            expected_state_version=expected_version,
            target_id=gate.id,
        )

        command, result = execute_durable_control_command(
            self.db,
            run=self.run,
            workflow=self.workflow,
            user=self.user,
            payload=payload,
        )
        self.db.commit()
        replay, replay_result = execute_durable_control_command(
            self.db,
            run=self.run,
            workflow=self.workflow,
            user=self.user,
            payload=payload,
        )

        self.assertEqual(command.id, replay.id)
        self.assertTrue(result["enqueue_run"])
        self.assertFalse(result["idempotent_replay"])
        self.assertFalse(replay_result["enqueue_run"])
        self.assertFalse(replay_result["cancel_worker"])
        self.assertTrue(replay_result["idempotent_replay"])
        self.assertEqual(result["attempt_ids"], replay_result["attempt_ids"])
        self.assertEqual("retrying", self.run.status.value)
        self.assertEqual(1, len(result["attempt_ids"]))
        with self.assertRaisesRegex(AgentControlCommandError, "过期状态"):
            execute_durable_control_command(
                self.db,
                run=self.run,
                workflow=self.workflow,
                user=self.user,
                payload=DurableControlCommandCreate(
                    command="cancel_run",
                    idempotency_key="stale-cancel-001",
                    expected_state_version=expected_version,
                    feedback="停止测试",
                ),
            )

    def test_cancel_command_converges_all_unstarted_tasks(self) -> None:
        command, result = execute_durable_control_command(
            self.db,
            run=self.run,
            workflow=self.workflow,
            user=self.user,
            payload=DurableControlCommandCreate(
                command="cancel_run",
                idempotency_key="cancel-run-001",
                expected_state_version=self.workflow.state_version,
                feedback="用户终止测试",
            ),
        )
        self.db.commit()

        self.assertEqual("applied", command.status)
        self.assertEqual("cancelled", result["workflow_status"])
        self.assertEqual(AgentRunStatus.cancelled, self.run.status)
        tasks = self.db.scalars(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == self.workflow.id
            )
        ).all()
        self.assertTrue(all(task.status == "cancelled" for task in tasks))
        self.assertEqual([], durable_control_state(self.db, workflow=self.workflow)["allowed_actions"])

    def test_unknown_effect_must_be_resolved_before_retry(self) -> None:
        task = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == self.workflow.id,
                DurableAgentTask.task_key == "research_topics",
            )
        )
        native_step = NativeAgentStep(
            run_id=self.run.id,
            sequence=1,
            step_type=NativeAgentStepType.tool_call,
            status=NativeAgentStepStatus.unknown,
            name="generate_image",
            tool_call_id="unknown-image-call",
            idempotency_key=f"native:{self.run.id}:unknown-image-call",
            attempts=1,
        )
        self.db.add(native_step)
        self.db.flush()
        effect = DurableAgentToolEffect(
            attempt_id=task.current_attempt_id,
            effect_kind="native_generate_image",
            idempotency_key=f"native-image-step:{native_step.id}",
            status="unknown",
        )
        self.db.add(effect)
        task.status = "blocked"
        self.workflow.status = "waiting_for_input"
        self.workflow.expected_input_kind = "unknown_effect_resolution"
        self.workflow.state_version += 1
        self.db.commit()
        state = durable_control_state(self.db, workflow=self.workflow)
        self.assertIn("resolve_unknown_effect", state["allowed_actions"])
        self.assertNotIn("retry_task", state["allowed_actions"])

        _, result = execute_durable_control_command(
            self.db,
            run=self.run,
            workflow=self.workflow,
            user=self.user,
            payload=DurableControlCommandCreate(
                command="resolve_unknown_effect",
                idempotency_key="resolve-effect-001",
                expected_state_version=self.workflow.state_version,
                target_id=effect.id,
                resolution="failed",
            ),
        )
        self.db.commit()

        self.assertEqual("failed", result["workflow_status"])
        self.assertEqual(NativeAgentStepStatus.failed, native_step.status)
        self.assertIsNotNone(native_step.finished_at)
        state = durable_control_state(self.db, workflow=self.workflow)
        self.assertIn("retry_task", state["allowed_actions"])
        _, retry_result = execute_durable_control_command(
            self.db,
            run=self.run,
            workflow=self.workflow,
            user=self.user,
            payload=DurableControlCommandCreate(
                command="retry_task",
                idempotency_key="retry-task-001",
                expected_state_version=self.workflow.state_version,
                target_id=task.id,
            ),
        )
        self.assertEqual(1, len(retry_result["attempt_ids"]))
        self.assertEqual("retrying", self.workflow.status)


if __name__ == "__main__":
    unittest.main()
