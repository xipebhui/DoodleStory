import unittest
from unittest.mock import patch

from datetime import timedelta

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.core.database import Base
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    DurableAgentArtifact,
    DurableAgentMediaBinding,
    DurableAgentPlanRevision,
    DurableAgentTask,
    DurableAgentToolEffect,
    DurableAgentWorkflow,
    FileAsset,
    GeneratedImage,
    GenerationTask,
    NativeAgentConversation,
    NativeAgentArticleApproval,
    NativeAgentArtifact,
    NativeAgentImage,
    NativeAgentRun,
    NativeAgentStep,
    Style,
    TaskPanel,
    User,
)
from app.models.enums import (
    AgentRunStatus,
    AgentSkillStatus,
    GeneratedImageStatus,
    NativeAgentStepStatus,
    NativeAgentStepType,
    FileAssetPurpose,
    ImageCountMode,
    StorageBackend,
    StyleStatus,
)
from app.schemas.native_agent import NativeAgentArtifactRead
from app.api.native_agent import get_durable_media_state
from app.services.image_generation import GeneratedImageFile
from app.services.agent_vision import InspectionResult
from app.services.native_agent_persistence import NativeAgentStore
from app.services.durable_agent_runtime import (
    claim_attempt,
    add_supplement_research_task,
    bind_panel_image,
    bind_native_agent_image,
    initialize_workflow,
    inspect_pending_native_media,
    mirror_native_article_approval,
    open_gate,
    open_image_quality_gate,
    record_artifact,
    record_image_quality,
    register_visual_plan,
    resolve_gate,
    recover_attempts,
    request_panel_rerun,
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
            model_route_snapshot="huomiao_responses",
            model_provider_snapshot="huomiao",
            model_api_shape_snapshot="responses",
            skill_name_snapshot=version.name_snapshot,
            skill_version_snapshot=version.version,
            skill_content_hash_snapshot=version.content_hash,
            style_reference_urls_json="[]",
        )
        self.db.add(self.run)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def _approve_visual_plan(
        self,
        workflow: DurableAgentWorkflow,
        panel_keys: list[str],
    ) -> None:
        editorial_gate = self.db.scalar(
            select(DurableAgentTask).where(
                DurableAgentTask.workflow_id == workflow.id,
                DurableAgentTask.task_key == "editorial_review_gate",
            )
        )
        editorial_gate.status = "succeeded"
        _, gate = register_visual_plan(
            self.db,
            workflow=workflow,
            content={
                "panels": [
                    {
                        "panel_key": panel_key,
                        "prompt": f"prompt for {panel_key}",
                    }
                    for panel_key in panel_keys
                ]
            },
        )
        resolve_gate(
            self.db,
            gate=gate,
            user=self.user,
            decision="approve",
            feedback=None,
        )

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

    def test_visual_plan_requires_approved_editorial_review(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        with self.assertRaises(RuntimeError):
            register_visual_plan(
                self.db,
                workflow=workflow,
                content={
                    "panels": [
                        {"panel_key": "cover", "prompt": "封面画面"}
                    ]
                },
            )

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

    def test_panel_rerun_only_changes_target_binding(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        self._approve_visual_plan(workflow, ["1", "2"])
        style = Style(
            name="media-style",
            status=StyleStatus.active,
            style_prompt="style",
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
        )
        self.db.add(style)
        self.db.flush()
        generation_task = GenerationTask(
            owner_user_id=self.user.id,
            display_title="media task",
            original_text="story",
            image_count_mode=ImageCountMode.fixed,
            requested_image_count=2,
            style_id=style.id,
            style_name_snapshot=style.name,
            style_prompt_snapshot=style.style_prompt,
            image_model_name_snapshot=style.image_model_name,
            style_aspect_ratio_snapshot=style.aspect_ratio,
        )
        self.db.add(generation_task)
        self.db.flush()
        first_panel = TaskPanel(
            task_id=generation_task.id,
            panel_order=1,
            original_text_segment="first",
        )
        second_panel = TaskPanel(
            task_id=generation_task.id,
            panel_order=2,
            original_text_segment="second",
        )
        self.db.add_all([first_panel, second_panel])
        self.db.flush()
        first_asset = FileAsset(
            purpose=FileAssetPurpose.generated_image,
            storage_backend=StorageBackend.local,
            storage_key="durable-media/first.png",
            content_type="image/png",
            byte_size=10,
        )
        second_asset = FileAsset(
            purpose=FileAssetPurpose.generated_image,
            storage_backend=StorageBackend.local,
            storage_key="durable-media/second.png",
            content_type="image/png",
            byte_size=10,
        )
        self.db.add_all([first_asset, second_asset])
        self.db.flush()
        first_image = GeneratedImage(
            task_id=generation_task.id,
            panel_id=first_panel.id,
            owner_user_id=self.user.id,
            status=GeneratedImageStatus.succeeded,
            generation_number=1,
            is_current=True,
            image_model_name_snapshot=style.image_model_name,
            asset_id=first_asset.id,
        )
        second_image = GeneratedImage(
            task_id=generation_task.id,
            panel_id=second_panel.id,
            owner_user_id=self.user.id,
            status=GeneratedImageStatus.succeeded,
            generation_number=1,
            is_current=True,
            image_model_name_snapshot=style.image_model_name,
            asset_id=second_asset.id,
        )
        self.db.add_all([first_image, second_image])
        self.db.flush()
        first_binding = bind_panel_image(
            self.db,
            workflow=workflow,
            generated_image=first_image,
        )
        second_binding = bind_panel_image(
            self.db,
            workflow=workflow,
            generated_image=second_image,
        )
        record_image_quality(
            self.db,
            binding=first_binding,
            verdict="changes_required",
            summary="表情不对",
            details={"panel_id": first_panel.id},
        )
        record_image_quality(
            self.db,
            binding=second_binding,
            verdict="accepted",
            summary="通过",
            details={"panel_id": second_panel.id},
        )
        attempt = request_panel_rerun(
            self.db,
            binding=first_binding,
            user_feedback="人物表情更紧张",
        )
        self.db.commit()
        self.assertEqual(first_binding.image_task_id, attempt.task_id)
        self.assertEqual("rerun_requested", first_binding.status)
        self.assertEqual("accepted", second_binding.status)
        self.assertEqual(
            2,
            len(
                self.db.scalars(
                    select(DurableAgentMediaBinding).where(
                        DurableAgentMediaBinding.workflow_id == workflow.id
                    )
                ).all()
            ),
        )

    def test_image_quality_gate_requires_all_panel_verdicts(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        self._approve_visual_plan(workflow, ["1"])
        style = Style(
            name="quality-style",
            status=StyleStatus.active,
            style_prompt="style",
            image_model_name="gpt-image-2",
            aspect_ratio="3:4",
        )
        self.db.add(style)
        self.db.flush()
        task = GenerationTask(
            owner_user_id=self.user.id,
            display_title="quality task",
            original_text="story",
            image_count_mode=ImageCountMode.fixed,
            requested_image_count=1,
            style_id=style.id,
            style_name_snapshot=style.name,
            style_prompt_snapshot=style.style_prompt,
            image_model_name_snapshot=style.image_model_name,
            style_aspect_ratio_snapshot=style.aspect_ratio,
        )
        self.db.add(task)
        self.db.flush()
        panel = TaskPanel(
            task_id=task.id,
            panel_order=1,
            original_text_segment="panel",
        )
        asset = FileAsset(
            purpose=FileAssetPurpose.generated_image,
            storage_backend=StorageBackend.local,
            storage_key="durable-media/quality.png",
            content_type="image/png",
            byte_size=10,
        )
        self.db.add_all([panel, asset])
        self.db.flush()
        image = GeneratedImage(
            task_id=task.id,
            panel_id=panel.id,
            owner_user_id=self.user.id,
            status=GeneratedImageStatus.succeeded,
            generation_number=1,
            is_current=True,
            image_model_name_snapshot=style.image_model_name,
            asset_id=asset.id,
        )
        self.db.add(image)
        self.db.flush()
        binding = bind_panel_image(
            self.db,
            workflow=workflow,
            generated_image=image,
        )
        with self.assertRaises(RuntimeError):
            open_image_quality_gate(self.db, workflow=workflow)
        record_image_quality(
            self.db,
            binding=binding,
            verdict="accepted",
            summary="通过",
            details={},
        )
        gate = open_image_quality_gate(self.db, workflow=workflow)
        self.assertEqual("image_quality_review", gate.purpose)

    def test_native_image_binding_has_effect_and_quality_task(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        self._approve_visual_plan(workflow, ["cover"])
        asset = FileAsset(
            purpose=FileAssetPurpose.generated_image,
            storage_backend=StorageBackend.local,
            storage_key="durable-media/native.png",
            content_type="image/png",
            byte_size=10,
        )
        self.db.add(asset)
        self.db.flush()
        step = NativeAgentStep(
            run_id=self.run.id,
            sequence=1,
            step_type=NativeAgentStepType.tool_call,
            status=NativeAgentStepStatus.succeeded,
            name="generate_image",
            idempotency_key="native-image-test",
            attempts=1,
        )
        image = NativeAgentImage(
            run_id=self.run.id,
            asset_id=asset.id,
            prompt="image prompt",
            image_model_snapshot="gpt-image-2",
            aspect_ratio_snapshot="3:4",
            provider_request_id="provider-request",
        )
        self.db.add_all([step, image])
        self.db.flush()
        binding = bind_native_agent_image(
            self.db,
            workflow=workflow,
            native_image=image,
            native_step=step,
        )
        self.db.commit()
        self.assertEqual(image.id, binding.native_agent_image_id)
        self.assertIsNone(binding.generated_image_id)
        quality_task = self.db.get(DurableAgentTask, binding.quality_task_id)
        self.assertEqual("ready", quality_task.status)

    def test_native_image_tool_completion_binds_durable_media(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        self._approve_visual_plan(workflow, ["cover"])
        self.db.commit()
        store = NativeAgentStore(self.run.id, session_factory=self.Session)
        step = store.prepare_tool(
            tool_call_id="call-cover",
            prompt="封面画面",
            provider="qy",
        )
        store.start_tool(step.id)
        completed = store.complete_tool(
            step.id,
            prompt="封面画面",
            generated=GeneratedImageFile(
                storage_backend=StorageBackend.local,
                storage_key="durable-media/native-tool.png",
                byte_size=10,
                checksum_sha256="a" * 64,
                content_type="image/png",
                original_filename="native-tool.png",
                provider_request_id="provider-native-tool",
                width=1024,
                height=1792,
            ),
            image_model="gpt-image-2",
            aspect_ratio="9:16",
            provider="qy",
        )
        self.db.expire_all()
        binding = self.db.scalar(
            select(DurableAgentMediaBinding).where(
                DurableAgentMediaBinding.workflow_id == workflow.id,
                DurableAgentMediaBinding.native_agent_image_id == completed.image_id,
            )
        )
        self.assertIsNotNone(binding)
        self.assertEqual("cover", binding.plan_panel_key)
        image_task = self.db.get(DurableAgentTask, binding.image_task_id)
        self.assertEqual("succeeded", image_task.status)
        effect = self.db.scalar(
            select(DurableAgentToolEffect).where(
                DurableAgentToolEffect.attempt_id == image_task.current_attempt_id
            )
        )
        self.assertEqual("succeeded", effect.status)
        self.assertEqual("provider-native-tool", effect.provider_request_id)
        with patch(
            "app.services.agent_vision.inspect_image_asset",
            return_value=(
                InspectionResult(
                    verdict="accept",
                    scores={
                        "story_alignment": 1.0,
                        "character_consistency": 1.0,
                        "continuity": 1.0,
                        "text_accuracy": 1.0,
                        "visual_artifacts": 1.0,
                    },
                ),
                "text_fallback",
                "vision-model",
                20,
            ),
        ):
            inspected = inspect_pending_native_media(
                native_run_id=self.run.id,
                session_factory=self.Session,
            )
        self.assertEqual(1, inspected)
        self.db.expire_all()
        self.assertEqual("accepted", self.db.get(DurableAgentMediaBinding, binding.id).status)

    def test_failed_native_image_effect_creates_explicit_retry_attempt(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        self._approve_visual_plan(workflow, ["cover"])
        self.db.commit()
        store = NativeAgentStore(self.run.id, session_factory=self.Session)
        first_step = store.prepare_tool(
            tool_call_id="call-cover-failed",
            prompt="封面画面",
            provider="qy",
        )
        store.start_tool(first_step.id)
        store.fail_tool(first_step.id, RuntimeError("provider rejected request"))
        second_step = store.prepare_tool(
            tool_call_id="call-cover-retry",
            prompt="修正后的封面画面",
            provider="qy",
        )
        self.db.expire_all()
        first_effect = self.db.scalar(
            select(DurableAgentToolEffect).where(
                DurableAgentToolEffect.idempotency_key
                == f"native-image-step:{first_step.id}"
            )
        )
        second_effect = self.db.scalar(
            select(DurableAgentToolEffect).where(
                DurableAgentToolEffect.idempotency_key
                == f"native-image-step:{second_step.id}"
            )
        )
        self.assertEqual("failed", first_effect.status)
        self.assertEqual("prepared", second_effect.status)
        self.assertNotEqual(first_effect.attempt_id, second_effect.attempt_id)

    def test_media_state_is_owner_scoped(self) -> None:
        workflow = initialize_workflow(self.db, native_run=self.run)
        self._approve_visual_plan(workflow, ["cover"])
        other_user = User(email="other@example.com", password_hash="hash")
        self.db.add(other_user)
        self.db.commit()
        owned = get_durable_media_state(
            self.run.id,
            user=self.user,
            db=self.db,
        )
        self.assertEqual(workflow.id, owned.data["workflow_id"])
        with self.assertRaises(HTTPException) as raised:
            get_durable_media_state(
                self.run.id,
                user=other_user,
                db=self.db,
            )
        self.assertEqual(404, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
