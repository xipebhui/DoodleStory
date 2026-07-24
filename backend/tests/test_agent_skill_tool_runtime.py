from contextlib import contextmanager
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import (
    AgentConversation,
    AgentRun,
    AgentStep,
    GeneratedImage,
    GenerationTask,
    Style,
    TaskPanel,
    User,
)
from app.models.enums import (
    AgentRunStatus,
    AgentStepType,
    GeneratedImageStatus,
    ImageCountMode,
    PanelType,
    PromptStatus,
    StoryInputMode,
    StyleReferenceMode,
    StyleStatus,
    TaskStatus,
)
from app.services.agent_skill_registry import (
    SkillNotFoundError,
    SkillRegistry,
    SkillRegistryError,
)
from app.schemas.agent import ComicPlan
from app.services.agent_hitl import create_comic_plan_artifact, decide_approval
from app.services.agent_tool_runtime import (
    GenericToolExecutor,
    StrictToolModel,
    ToolAdapterResult,
    ToolAuthorizationError,
    ToolDefinition,
    ToolInputValidationError,
    ToolRegistry,
    ToolNotRegisteredError,
    build_runtime_context,
    create_default_tool_registry,
)


def write_skill(
    root: Path,
    directory: str,
    *,
    name: str | None = None,
    version: str = "1",
    body: str = "SECRET SKILL BODY",
) -> None:
    skill_dir = root / directory
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name or directory}",
                f"description: {directory} description",
                f"version: {version}",
                "---",
                "",
                body,
            ]
        ),
        encoding="utf-8",
    )


class SkillRegistryTests(unittest.TestCase):
    def test_catalog_is_bounded_metadata_and_load_returns_complete_content(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            write_skill(root, "idea-to-comic")
            registry = SkillRegistry(root)

            catalog = registry.catalog()
            loaded = registry.load("idea-to-comic")

        self.assertEqual(1, len(catalog))
        self.assertNotIn("instructions", catalog[0])
        self.assertNotIn("SECRET SKILL BODY", json.dumps(catalog))
        self.assertIn("SECRET SKILL BODY", loaded.instructions)
        self.assertRegex(loaded.content_hash, r"^sha256:[0-9a-f]{64}$")

    def test_path_traversal_and_unregistered_skill_are_rejected(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            write_skill(root, "safe-skill")
            registry = SkillRegistry(root)
            for name in ("../safe-skill", "/tmp/safe-skill", "missing"):
                with self.subTest(name=name), self.assertRaises(SkillNotFoundError):
                    registry.load(name)

    def test_missing_file_duplicate_name_and_invalid_version_are_rejected(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "missing-file").mkdir()
            with self.assertRaisesRegex(SkillRegistryError, "缺少 SKILL.md"):
                SkillRegistry(root)

        with TemporaryDirectory() as temp:
            root = Path(temp)
            write_skill(root, "alpha")
            write_skill(root, "beta", name="alpha")
            with self.assertRaisesRegex(SkillRegistryError, "name 重复"):
                SkillRegistry(root)

        with TemporaryDirectory() as temp:
            root = Path(temp)
            write_skill(root, "invalid-version", version="0")
            with self.assertRaisesRegex(SkillRegistryError, "正整数"):
                SkillRegistry(root)


class EchoInput(StrictToolModel):
    value: str


class EchoOutput(StrictToolModel):
    echoed: str


class AgentToolRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        with self.Session() as db:
            user = User(email="runtime-tools@example.com", password_hash="hash")
            conversation = AgentConversation(owner=user, title="Tool Runtime")
            run = AgentRun(conversation=conversation, turn_id="turn-1")
            db.add_all([user, conversation, run])
            db.commit()
            self.user_id = user.id
            self.run_id = run.id

    def create_task_and_panel(self) -> tuple[str, str]:
        with self.Session() as db:
            run = db.get(AgentRun, self.run_id)
            style = Style(
                name="Runtime style",
                status=StyleStatus.active,
                image_model_name="gpt-image-2",
                aspect_ratio="3:4",
                style_prompt="runtime prompt",
            )
            db.add(style)
            db.flush()
            task = GenerationTask(
                owner_user_id=self.user_id,
                display_title="Runtime task",
                original_text="runtime",
                story_input_mode=StoryInputMode.adapted,
                image_count_mode=ImageCountMode.fixed,
                requested_image_count=2,
                use_character_references=False,
                last_panel_real_photo=False,
                remove_image_text=False,
                style_id=style.id,
                style_name_snapshot="runtime style",
                style_prompt_snapshot="runtime prompt",
                image_model_name_snapshot="gpt-image-2",
                style_aspect_ratio_snapshot="3:4",
                style_reference_mode_snapshot=StyleReferenceMode.prompt,
                status=TaskStatus.running,
            )
            db.add(task)
            db.flush()
            panel = TaskPanel(
                task_id=task.id,
                panel_order=1,
                panel_type=PanelType.scene,
                original_text_segment="一个场景",
                prompt_status=PromptStatus.generated,
                generated_prompt="runtime prompt",
            )
            db.add(panel)
            db.add(
                TaskPanel(
                    task_id=task.id,
                    panel_order=2,
                    panel_type=PanelType.scene,
                    original_text_segment="后续场景",
                    prompt_status=PromptStatus.generated,
                    generated_prompt="第二格最终指令",
                )
            )
            run.task_id = task.id
            plan = ComicPlan.model_validate(
                {
                    "schema_version": 1,
                    "title": "Runtime task",
                    "story_summary": "两个连续测试场景",
                    "aspect_ratio": "3:4",
                    "style_ref_id": style.id,
                    "panels": [
                        {
                            "panel_key": "panel-1",
                            "story_beat": "一个场景",
                            "visual_goal": "测试第一格",
                            "image_prompt": "单图最终指令",
                            "required_text": [],
                        },
                        {
                            "panel_key": "panel-2",
                            "story_beat": "后续场景",
                            "visual_goal": "测试第二格",
                            "image_prompt": "第二格最终指令",
                            "required_text": [],
                        },
                    ],
                    "estimated_image_credits": 2,
                }
            )
            _, approval = create_comic_plan_artifact(db, run=run, plan=plan)
            decide_approval(
                db,
                approval=approval,
                user_id=self.user_id,
                decision="approve",
                feedback=None,
            )
            db.commit()
            return task.id, panel.id

    def test_load_skill_persists_version_hash_loaded_at_and_reuses_result(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            write_skill(root, "idea-to-comic")
            registry = create_default_tool_registry(SkillRegistry(root))
            executor = GenericToolExecutor(registry)
            with self.Session() as db:
                run = db.get(AgentRun, self.run_id)
                result = executor.execute(
                    db,
                    run=run,
                    tool_name="load_skill",
                    arguments={"skill_name": "idea-to-comic"},
                    idempotency_key=f"agent:{run.id}:load_skill:idea-to-comic",
                )
                repeated = executor.execute(
                    db,
                    run=run,
                    tool_name="load_skill",
                    arguments={"skill_name": "idea-to-comic"},
                    idempotency_key=f"agent:{run.id}:load_skill:idea-to-comic",
                )
                steps = db.scalars(
                    select(AgentStep)
                    .where(AgentStep.run_id == run.id)
                    .order_by(AgentStep.sequence)
                ).all()

        self.assertEqual("completed", result.state)
        self.assertTrue(repeated.replayed)
        self.assertEqual(2, len(steps))
        self.assertEqual(
            [AgentStepType.tool_call, AgentStepType.tool_result],
            [step.step_type for step in steps],
        )
        output = json.loads(steps[-1].output_ref)
        self.assertEqual(1, output["version"])
        self.assertRegex(output["content_hash"], r"^sha256:")
        self.assertTrue(output["loaded_at"].endswith("Z"))
        self.assertIn("SECRET SKILL BODY", output["instructions"])

    def test_unregistered_tool_and_extra_parameters_are_rejected_without_step(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            write_skill(root, "idea-to-comic")
            executor = GenericToolExecutor(
                create_default_tool_registry(SkillRegistry(root))
            )
            with self.Session() as db:
                run = db.get(AgentRun, self.run_id)
                with self.assertRaises(ToolNotRegisteredError):
                    executor.execute(
                        db,
                        run=run,
                        tool_name="missing_tool",
                        arguments={},
                        idempotency_key="missing-tool",
                    )
                with self.assertRaises(ToolInputValidationError):
                    executor.execute(
                        db,
                        run=run,
                        tool_name="load_skill",
                        arguments={
                            "skill_name": "idea-to-comic",
                            "database_session": "forbidden",
                        },
                        idempotency_key="invalid-load-skill",
                    )
                step_count = db.scalar(select(func.count(AgentStep.id)))
        self.assertEqual(0, step_count)

    def test_side_effect_adapter_observes_committed_call_step_first(self) -> None:
        observed_step_ids: list[str] = []

        def adapter(db, context, arguments, call_step):
            del db, context
            with self.Session() as independent_db:
                persisted = independent_db.get(AgentStep, call_step.id)
                self.assertIsNotNone(persisted)
                observed_step_ids.append(persisted.id)
            parsed = EchoInput.model_validate(arguments)
            return ToolAdapterResult(
                state="completed",
                output={"echoed": parsed.value},
            )

        registry = ToolRegistry(
            [
                ToolDefinition(
                    name="echo_side_effect",
                    input_model=EchoInput,
                    output_model=EchoOutput,
                    has_side_effects=True,
                    requires_authorized_resources=False,
                    may_wait=False,
                    budget_kind="none",
                    adapter=adapter,
                )
            ]
        )
        with self.Session() as db:
            run = db.get(AgentRun, self.run_id)
            result = GenericToolExecutor(registry).execute(
                db,
                run=run,
                tool_name="echo_side_effect",
                arguments={"value": "ok"},
                idempotency_key=f"agent:{run.id}:echo",
            )
        self.assertEqual([result.call_step_id], observed_step_ids)

    def test_generate_image_wait_restart_replay_and_result_are_idempotent(self) -> None:
        task_id, panel_id = self.create_task_and_panel()
        recorded: list[tuple[str, dict[str, object]]] = []

        @contextmanager
        def record_span(name, *, attributes, **kwargs):
            del kwargs
            copied = dict(attributes)
            recorded.append((name, copied))
            yield None

        with patch(
            "app.services.agent_tool_runtime.agent_span",
            side_effect=record_span,
        ):
            with self.Session() as db:
                run = db.get(AgentRun, self.run_id)
                context = build_runtime_context(db, run, image_budget_limit=1)
                executor = GenericToolExecutor(create_default_tool_registry())
                first = executor.execute(
                    db,
                    run=run,
                    tool_name="generate_image",
                    arguments={
                        "panel_key": "panel-1",
                        "purpose": "panel_image",
                        "prompt": "单图最终指令",
                        "aspect_ratio": "3:4",
                        "reference_image_ids": [],
                    },
                    idempotency_key=f"agent:{run.id}:generate_image:panel-1",
                    context=context,
                )

            with self.Session() as db:
                run = db.get(AgentRun, self.run_id)
                restarted_executor = GenericToolExecutor(
                    create_default_tool_registry()
                )
                replay = restarted_executor.execute(
                    db,
                    run=run,
                    tool_name="generate_image",
                    arguments={
                        "panel_key": "panel-1",
                        "purpose": "panel_image",
                        "prompt": "单图最终指令",
                        "aspect_ratio": "3:4",
                        "reference_image_ids": [],
                    },
                    idempotency_key=f"agent:{run.id}:generate_image:panel-1",
                    context=build_runtime_context(
                        db,
                        run,
                        image_budget_limit=1,
                    ),
                )
                image = db.scalar(
                    select(GeneratedImage).where(GeneratedImage.task_id == task_id)
                )
                image.status = GeneratedImageStatus.failed
                image.error_code = "InjectedFailure"
                image.error_message = "受控失败"
                db.commit()
                completed = restarted_executor.complete_waiting(
                    db,
                    run=run,
                    idempotency_key=f"agent:{run.id}:generate_image:panel-1",
                    output={
                        "status": "failed",
                        "panel_key": "panel-1",
                        "error_code": "InjectedFailure",
                        "message": "受控失败",
                        "retryable": False,
                    },
                )
                repeated = restarted_executor.complete_waiting(
                    db,
                    run=run,
                    idempotency_key=f"agent:{run.id}:generate_image:panel-1",
                    output={
                        "status": "failed",
                        "panel_key": "panel-1",
                        "error_code": "InjectedFailure",
                        "message": "受控失败",
                        "retryable": False,
                    },
                )
                image_count = db.scalar(
                    select(func.count(GeneratedImage.id)).where(
                        GeneratedImage.panel_id == panel_id
                    )
                )
                result_count = db.scalar(
                    select(func.count(AgentStep.id)).where(
                        AgentStep.run_id == run.id,
                        AgentStep.step_type == AgentStepType.tool_result,
                    )
                )

        self.assertEqual("waiting", first.state)
        self.assertTrue(replay.replayed)
        self.assertEqual(1, image_count)
        self.assertEqual(1, result_count)
        self.assertFalse(completed.replayed)
        self.assertTrue(repeated.replayed)
        tool_spans = [
            attributes
            for name, attributes in recorded
            if name in {"agent.tool_call", "agent.tool_result"}
        ]
        self.assertEqual(
            {first.call_step_id, completed.result_step_id},
            {attributes["agent_step_id"] for attributes in tool_spans},
        )

    def test_cancelled_run_does_not_start_image_side_effect(self) -> None:
        self.create_task_and_panel()
        with self.Session() as db:
            run = db.get(AgentRun, self.run_id)
            run.status = AgentRunStatus.cancel_requested
            db.commit()
            with self.assertRaises(ToolAuthorizationError):
                GenericToolExecutor(create_default_tool_registry()).execute(
                    db,
                    run=run,
                    tool_name="generate_image",
                    arguments={
                        "panel_key": "panel-1",
                        "purpose": "panel_image",
                        "prompt": "不应执行",
                        "aspect_ratio": "3:4",
                        "reference_image_ids": [],
                    },
                    idempotency_key=f"agent:{run.id}:cancelled-image",
                    context=build_runtime_context(db, run, image_budget_limit=1),
                )
            self.assertEqual(0, db.scalar(select(func.count(GeneratedImage.id))))
            self.assertEqual(0, db.scalar(select(func.count(AgentStep.id))))


if __name__ == "__main__":
    unittest.main()
