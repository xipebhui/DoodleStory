from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AgentRun,
    AgentStep,
    GeneratedImage,
    GenerationTask,
    TaskPanel,
)
from app.models.enums import (
    AgentRunStatus,
    AgentStepStatus,
    AgentStepType,
    GeneratedImageJobKind,
    GeneratedImageSourceType,
    GeneratedImageStatus,
    GeneratedImageWorkflowStep,
)
from app.services.agent_observability import (
    agent_span,
    safe_idempotency_digest,
    set_span_result,
)
from app.services.agent_skill_registry import SkillRegistry, get_runtime_skill_registry


class AgentToolRuntimeError(RuntimeError):
    pass


class ToolNotRegisteredError(AgentToolRuntimeError):
    pass


class ToolInputValidationError(AgentToolRuntimeError):
    pass


class ToolAuthorizationError(AgentToolRuntimeError):
    pass


class ToolBudgetExceededError(AgentToolRuntimeError):
    pass


class ToolExecutionConflictError(AgentToolRuntimeError):
    pass


class StrictToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoadSkillInput(StrictToolModel):
    skill_name: str = Field(min_length=1, max_length=120)


class LoadSkillOutput(StrictToolModel):
    name: str
    version: int = Field(gt=0)
    content_hash: str
    loaded_at: str
    instructions: str


class GenerateImageInput(StrictToolModel):
    panel_key: str = Field(max_length=80, pattern=r"^panel-[1-9][0-9]*$")
    purpose: Literal["panel_image", "character_reference"]
    prompt: str = Field(min_length=1, max_length=20_000)
    aspect_ratio: str = Field(min_length=1, max_length=40)
    reference_image_ids: list[str] = Field(default_factory=list, max_length=16)
    revision_instruction: str | None = Field(default=None, min_length=1, max_length=4_000)


class GenerateImageOutput(StrictToolModel):
    status: Literal["succeeded", "failed"]
    panel_key: str
    image_version_id: str | None = None
    asset_id: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    provider: str | None = None
    model: str | None = None
    provider_request_id: str | None = None
    error_code: str | None = None
    message: str | None = None
    retryable: bool | None = None

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> "GenerateImageOutput":
        if self.status == "succeeded":
            if not self.image_version_id or not self.asset_id:
                raise ValueError("成功图片 Tool Output 必须包含 image_version_id 和 asset_id")
        elif not self.error_code or not self.message or self.retryable is None:
            raise ValueError("失败图片 Tool Output 必须包含 error_code、message 和 retryable")
        return self


@dataclass(frozen=True)
class RuntimeContext:
    run_id: str
    conversation_id: str
    owner_user_id: str
    task_id: str | None
    authorized_panels: dict[str, str]
    authorized_reference_image_ids: frozenset[str]
    image_budget_limit: int


@dataclass(frozen=True)
class ToolAdapterResult:
    state: Literal["completed", "waiting"]
    output: dict[str, Any] | None = None
    checkpoint: dict[str, Any] | None = None
    side_effect_created: bool = False


@dataclass(frozen=True)
class ToolExecutionResult:
    state: Literal["completed", "waiting"]
    call_step_id: str
    result_step_id: str | None
    output: dict[str, Any] | None
    checkpoint: dict[str, Any] | None
    replayed: bool


ToolAdapter = Callable[
    [Session, RuntimeContext, BaseModel, AgentStep],
    ToolAdapterResult,
]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    has_side_effects: bool
    requires_authorized_resources: bool
    may_wait: bool
    budget_kind: Literal["none", "image_call"]
    adapter: ToolAdapter

    def model_visible_definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(),
            "has_side_effects": self.has_side_effects,
            "requires_authorized_resources": self.requires_authorized_resources,
            "may_wait": self.may_wait,
            "budget_kind": self.budget_kind,
        }


class ToolRegistry:
    def __init__(self, definitions: list[ToolDefinition]):
        self._definitions: dict[str, ToolDefinition] = {}
        for definition in definitions:
            if definition.name in self._definitions:
                raise AgentToolRuntimeError(f"Tool 重复注册: {definition.name}")
            self._definitions[definition.name] = definition

    def get(self, tool_name: str) -> ToolDefinition:
        definition = self._definitions.get(tool_name)
        if definition is None:
            raise ToolNotRegisteredError(f"Tool 未注册: {tool_name}")
        return definition

    def catalog(self) -> list[dict[str, Any]]:
        return [
            self._definitions[name].model_visible_definition()
            for name in sorted(self._definitions)
        ]


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_object(value: str | None, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "")
    except (json.JSONDecodeError, TypeError) as exc:
        raise ToolExecutionConflictError(f"{label} checkpoint 无法读取") from exc
    if not isinstance(parsed, dict):
        raise ToolExecutionConflictError(f"{label} checkpoint 必须是 JSON object")
    return parsed


def _next_step_sequence(db: Session, run_id: str) -> int:
    maximum = db.scalar(select(func.max(AgentStep.sequence)).where(AgentStep.run_id == run_id))
    return int(maximum or 0) + 1


def build_runtime_context(
    db: Session,
    run: AgentRun,
    *,
    image_budget_limit: int | None = None,
) -> RuntimeContext:
    if run.conversation is None:
        raise ToolAuthorizationError("Agent Run 缺少 Conversation")
    authorized_panels: dict[str, str] = {}
    reference_ids: set[str] = set()
    if run.task_id is not None:
        task = db.get(GenerationTask, run.task_id)
        if task is None:
            raise ToolAuthorizationError("Agent Run 关联任务不存在")
        if task.owner_user_id != run.conversation.owner_user_id:
            raise ToolAuthorizationError("Agent Run 与任务 owner 不一致")
        panels = db.scalars(
            select(TaskPanel)
            .where(TaskPanel.task_id == task.id)
            .order_by(TaskPanel.panel_order)
        ).all()
        authorized_panels = {
            f"panel-{panel.panel_order}": panel.id
            for panel in panels
        }
        reference_ids = {
            reference.asset_id
            for reference in task.style_reference_images
        }

    limit = image_budget_limit
    if limit is None:
        limit = max(run.image_call_count, len(authorized_panels))
    return RuntimeContext(
        run_id=run.id,
        conversation_id=run.conversation_id,
        owner_user_id=run.conversation.owner_user_id,
        task_id=run.task_id,
        authorized_panels=authorized_panels,
        authorized_reference_image_ids=frozenset(reference_ids),
        image_budget_limit=limit,
    )


def _load_skill_adapter(
    registry: SkillRegistry,
) -> ToolAdapter:
    def adapter(
        db: Session,
        context: RuntimeContext,
        arguments: BaseModel,
        call_step: AgentStep,
    ) -> ToolAdapterResult:
        del db, context, call_step
        parsed = LoadSkillInput.model_validate(arguments)
        package = registry.load(parsed.skill_name)
        return ToolAdapterResult(
            state="completed",
            output=LoadSkillOutput(
                name=package.name,
                version=package.version,
                content_hash=package.content_hash,
                loaded_at=datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
                instructions=package.instructions,
            ).model_dump(),
        )

    return adapter


def _generate_image_adapter(
    db: Session,
    context: RuntimeContext,
    arguments: BaseModel,
    call_step: AgentStep,
) -> ToolAdapterResult:
    parsed = GenerateImageInput.model_validate(arguments)
    if parsed.purpose != "panel_image":
        raise ToolAuthorizationError("Sprint 113 generate_image 只允许 panel_image")
    panel_id = context.authorized_panels.get(parsed.panel_key)
    if panel_id is None or context.task_id is None:
        raise ToolAuthorizationError("panel_key 不属于当前 Agent Run 已授权任务")
    unknown_references = set(parsed.reference_image_ids).difference(
        context.authorized_reference_image_ids
    )
    if unknown_references:
        raise ToolAuthorizationError("generate_image 包含未授权参考图")

    panel = db.get(TaskPanel, panel_id)
    task = db.get(GenerationTask, context.task_id)
    if panel is None or task is None or panel.task_id != task.id:
        raise ToolAuthorizationError("generate_image 的任务与 Panel 关系无效")
    if task.owner_user_id != context.owner_user_id:
        raise ToolAuthorizationError("generate_image 任务 owner 不匹配")
    if parsed.aspect_ratio != task.style_aspect_ratio_snapshot:
        raise ToolAuthorizationError("generate_image 画面比例与任务风格快照不一致")

    existing = db.scalar(
        select(GeneratedImage).where(
            GeneratedImage.panel_id == panel.id,
            GeneratedImage.generation_number == 1,
        )
    )
    if existing is not None:
        checkpoint = {
            "status": existing.status.value,
            "image_job_id": existing.id,
            "task_id": task.id,
            "panel_id": panel.id,
        }
        return ToolAdapterResult(
            state="waiting",
            checkpoint=checkpoint,
            side_effect_created=False,
        )

    image = GeneratedImage(
        task_id=task.id,
        panel_id=panel.id,
        owner_user_id=context.owner_user_id,
        job_kind=GeneratedImageJobKind.panel_image,
        status=GeneratedImageStatus.queued,
        generation_number=1,
        is_current=False,
        source_type=GeneratedImageSourceType.initial,
        workflow_step=GeneratedImageWorkflowStep.generate_image,
        queued_at=datetime.utcnow(),
        queue_group=context.owner_user_id,
        image_prompt=parsed.prompt,
        image_text_json=panel.image_text_json,
        text_layout=panel.text_layout,
        final_prompt=parsed.prompt,
        image_model_name_snapshot=task.image_model_name_snapshot,
    )
    db.add(image)
    db.flush()
    return ToolAdapterResult(
        state="waiting",
        checkpoint={
            "status": "queued",
            "image_job_id": image.id,
            "task_id": task.id,
            "panel_id": panel.id,
        },
        side_effect_created=True,
    )


def create_default_tool_registry(
    skill_registry: SkillRegistry | None = None,
) -> ToolRegistry:
    selected_skills = skill_registry or get_runtime_skill_registry()
    return ToolRegistry(
        [
            ToolDefinition(
                name="load_skill",
                input_model=LoadSkillInput,
                output_model=LoadSkillOutput,
                has_side_effects=False,
                requires_authorized_resources=False,
                may_wait=False,
                budget_kind="none",
                adapter=_load_skill_adapter(selected_skills),
            ),
            ToolDefinition(
                name="generate_image",
                input_model=GenerateImageInput,
                output_model=GenerateImageOutput,
                has_side_effects=True,
                requires_authorized_resources=True,
                may_wait=True,
                budget_kind="image_call",
                adapter=_generate_image_adapter,
            ),
        ]
    )


class GenericToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    @staticmethod
    def _result_key(call_key: str) -> str:
        return f"{call_key}:result"

    @staticmethod
    def _wait_key(call_key: str) -> str:
        return f"{call_key}:wait"

    def _validate_input(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> BaseModel:
        try:
            return definition.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolInputValidationError(
                f"Tool {definition.name} 参数不符合 schema: {exc.errors(include_url=False)}"
            ) from exc

    @staticmethod
    def _validate_output(
        definition: ToolDefinition,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            return definition.output_model.model_validate(output).model_dump(
                exclude_none=True
            )
        except ValidationError as exc:
            raise AgentToolRuntimeError(
                f"Tool {definition.name} 输出不符合安全 schema"
            ) from exc

    @staticmethod
    def _ensure_can_execute(
        run: AgentRun,
        definition: ToolDefinition,
        context: RuntimeContext,
        arguments: BaseModel,
    ) -> None:
        if run.status in {AgentRunStatus.cancel_requested, AgentRunStatus.cancelled}:
            raise ToolAuthorizationError("Agent Run 已取消，不能启动新的 Tool 副作用")
        if definition.requires_authorized_resources:
            if context.task_id is None:
                raise ToolAuthorizationError(f"Tool {definition.name} 缺少已授权任务资源")
            if isinstance(arguments, GenerateImageInput):
                if arguments.panel_key not in context.authorized_panels:
                    raise ToolAuthorizationError("panel_key 未获当前 Agent Run 授权")
                if not set(arguments.reference_image_ids).issubset(
                    context.authorized_reference_image_ids
                ):
                    raise ToolAuthorizationError("参考图未获当前 Agent Run 授权")
        if (
            definition.budget_kind == "image_call"
            and run.image_call_count >= context.image_budget_limit
        ):
            raise ToolBudgetExceededError("本轮图片 Tool 调用预算已用完")

    def _load_replay(
        self,
        db: Session,
        *,
        definition: ToolDefinition,
        arguments: BaseModel,
        idempotency_key: str,
    ) -> ToolExecutionResult | None:
        call_step = db.scalar(
            select(AgentStep).where(AgentStep.idempotency_key == idempotency_key)
        )
        if call_step is None:
            return None
        if call_step.step_type != AgentStepType.tool_call:
            raise ToolExecutionConflictError("幂等键已被非 tool_call Step 使用")
        input_payload = _json_object(call_step.input_ref, label="tool_call")
        expected = {
            "tool": definition.name,
            "arguments": arguments.model_dump(exclude_none=True),
        }
        if input_payload != expected:
            raise ToolExecutionConflictError("同一 Tool 幂等键对应了不同调用")
        result_step = db.scalar(
            select(AgentStep).where(
                AgentStep.idempotency_key == self._result_key(idempotency_key)
            )
        )
        if result_step is not None:
            output = _json_object(result_step.output_ref, label="tool_result")
            return ToolExecutionResult(
                state="completed",
                call_step_id=call_step.id,
                result_step_id=result_step.id,
                output=output,
                checkpoint=None,
                replayed=True,
            )
        checkpoint = (
            _json_object(call_step.output_ref, label="tool_call")
            if call_step.output_ref
            else None
        )
        if checkpoint is not None:
            return ToolExecutionResult(
                state="waiting",
                call_step_id=call_step.id,
                result_step_id=None,
                output=None,
                checkpoint=checkpoint,
                replayed=True,
            )
        return ToolExecutionResult(
            state="waiting",
            call_step_id=call_step.id,
            result_step_id=None,
            output=None,
            checkpoint=None,
            replayed=True,
        )

    def execute(
        self,
        db: Session,
        *,
        run: AgentRun,
        tool_name: str,
        arguments: dict[str, Any],
        idempotency_key: str,
        context: RuntimeContext | None = None,
    ) -> ToolExecutionResult:
        definition = self.registry.get(tool_name)
        parsed_arguments = self._validate_input(definition, arguments)
        runtime_context = context or build_runtime_context(db, run)
        replay = self._load_replay(
            db,
            definition=definition,
            arguments=parsed_arguments,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            if replay.state == "completed" or replay.checkpoint is not None:
                return replay
        if replay is None:
            self._ensure_can_execute(run, definition, runtime_context, parsed_arguments)
            call_step = AgentStep(
                run_id=run.id,
                sequence=_next_step_sequence(db, run.id),
                step_type=AgentStepType.tool_call,
                status=AgentStepStatus.running,
                attempt=1,
                idempotency_key=idempotency_key,
                input_ref=_json(
                    {
                        "tool": definition.name,
                        "arguments": parsed_arguments.model_dump(exclude_none=True),
                    }
                ),
                started_at=datetime.utcnow(),
            )
            db.add(call_step)
            db.commit()
            db.refresh(call_step)
        else:
            call_step = db.get(AgentStep, replay.call_step_id)
            if call_step is None:
                raise ToolExecutionConflictError("Tool call Step 在恢复时不存在")
            self._ensure_can_execute(run, definition, runtime_context, parsed_arguments)

        span_name = "agent.skill_load" if tool_name == "load_skill" else "agent.tool_call"
        attributes = {
            "tool_name": definition.name,
            "agent_step_id": call_step.id,
            "idempotency_digest": safe_idempotency_digest(idempotency_key),
            "task_id": runtime_context.task_id,
            "tool_status": "running",
        }
        with agent_span(
            span_name,
            agent_run_id=run.id,
            span_type="TOOL",
            attributes=attributes,
        ) as span:
            try:
                adapter_result = definition.adapter(
                    db,
                    runtime_context,
                    parsed_arguments,
                    call_step,
                )
                if adapter_result.state == "completed":
                    if adapter_result.output is None:
                        raise AgentToolRuntimeError(
                            f"Tool {definition.name} completed 但没有 output"
                        )
                    output = self._validate_output(definition, adapter_result.output)
                    result = self._persist_result(
                        db,
                        run=run,
                        definition=definition,
                        call_step=call_step,
                        idempotency_key=idempotency_key,
                        output=output,
                    )
                    if tool_name == "load_skill":
                        set_span_result(
                            span,
                            {
                                "tool_status": "succeeded",
                                "agent_step_id": call_step.id,
                                "skill_name": output["name"],
                                "skill_version": output["version"],
                                "content_hash": output["content_hash"],
                                "loaded_at": output["loaded_at"],
                            },
                        )
                    return result
                if not definition.may_wait or adapter_result.checkpoint is None:
                    raise AgentToolRuntimeError(
                        f"Tool {definition.name} 返回了无效 waiting checkpoint"
                    )
                call_step.status = AgentStepStatus.succeeded
                call_step.output_ref = _json(adapter_result.checkpoint)
                call_step.finished_at = datetime.utcnow()
                if adapter_result.side_effect_created:
                    run.image_call_count += 1
                run.status = AgentRunStatus.waiting_for_tool
                wait_key = self._wait_key(idempotency_key)
                wait_step = db.scalar(
                    select(AgentStep).where(AgentStep.idempotency_key == wait_key)
                )
                if wait_step is None:
                    wait_step = AgentStep(
                        run_id=run.id,
                        sequence=_next_step_sequence(db, run.id),
                        step_type=AgentStepType.wait,
                        status=AgentStepStatus.running,
                        attempt=1,
                        idempotency_key=wait_key,
                        input_ref=_json(adapter_result.checkpoint),
                        started_at=datetime.utcnow(),
                    )
                    db.add(wait_step)
                db.commit()
                set_span_result(
                    span,
                    {
                        "tool_status": "queued",
                        "agent_step_id": call_step.id,
                        **adapter_result.checkpoint,
                    },
                )
                return ToolExecutionResult(
                    state="waiting",
                    call_step_id=call_step.id,
                    result_step_id=None,
                    output=None,
                    checkpoint=adapter_result.checkpoint,
                    replayed=replay is not None,
                )
            except Exception as exc:
                db.rollback()
                persisted_call = db.get(AgentStep, call_step.id)
                if persisted_call is not None and persisted_call.status == AgentStepStatus.running:
                    persisted_call.status = AgentStepStatus.failed
                    persisted_call.error_code = type(exc).__name__
                    persisted_call.error_message = str(exc)
                    persisted_call.finished_at = datetime.utcnow()
                    db.commit()
                raise

    def _persist_result(
        self,
        db: Session,
        *,
        run: AgentRun,
        definition: ToolDefinition,
        call_step: AgentStep,
        idempotency_key: str,
        output: dict[str, Any],
    ) -> ToolExecutionResult:
        result_key = self._result_key(idempotency_key)
        result_step = db.scalar(
            select(AgentStep).where(AgentStep.idempotency_key == result_key)
        )
        if result_step is None:
            result_step = AgentStep(
                run_id=run.id,
                sequence=_next_step_sequence(db, run.id),
                step_type=AgentStepType.tool_result,
                status=AgentStepStatus.succeeded,
                attempt=1,
                idempotency_key=result_key,
                input_ref=_json({"tool_call_step_id": call_step.id}),
                output_ref=_json(output),
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
            db.add(result_step)
            db.flush()
        elif _json_object(result_step.output_ref, label="tool_result") != output:
            raise ToolExecutionConflictError("同一 Tool result 幂等键对应了不同输出")
        call_step.status = AgentStepStatus.succeeded
        call_step.finished_at = call_step.finished_at or datetime.utcnow()
        wait_step = db.scalar(
            select(AgentStep).where(
                AgentStep.idempotency_key == self._wait_key(idempotency_key)
            )
        )
        if wait_step is not None and wait_step.status == AgentStepStatus.running:
            wait_step.status = AgentStepStatus.succeeded
            wait_step.output_ref = _json(output)
            wait_step.finished_at = datetime.utcnow()
        db.commit()
        return ToolExecutionResult(
            state="completed",
            call_step_id=call_step.id,
            result_step_id=result_step.id,
            output=output,
            checkpoint=None,
            replayed=False,
        )

    def complete_waiting(
        self,
        db: Session,
        *,
        run: AgentRun,
        idempotency_key: str,
        output: dict[str, Any],
        trace_attributes: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        call_step = db.scalar(
            select(AgentStep).where(
                AgentStep.idempotency_key == idempotency_key,
                AgentStep.run_id == run.id,
                AgentStep.step_type == AgentStepType.tool_call,
            )
        )
        if call_step is None:
            raise ToolExecutionConflictError("等待中的 Tool call Step 不存在")
        call_payload = _json_object(call_step.input_ref, label="tool_call")
        tool_name = call_payload.get("tool")
        if not isinstance(tool_name, str):
            raise ToolExecutionConflictError("Tool call checkpoint 缺少 tool name")
        definition = self.registry.get(tool_name)
        validated_output = self._validate_output(definition, output)
        result_key = self._result_key(idempotency_key)
        existing_result = db.scalar(
            select(AgentStep).where(AgentStep.idempotency_key == result_key)
        )
        result = self._persist_result(
            db,
            run=run,
            definition=definition,
            call_step=call_step,
            idempotency_key=idempotency_key,
            output=validated_output,
        )
        if existing_result is None:
            checkpoint = _json_object(call_step.output_ref, label="tool_call")
            with agent_span(
                "agent.tool_result",
                agent_run_id=run.id,
                span_type="TOOL",
                attributes={
                    "tool_name": tool_name,
                    "agent_step_id": result.result_step_id,
                    "idempotency_digest": safe_idempotency_digest(result_key),
                    "task_id": checkpoint.get("task_id"),
                    "panel_id": checkpoint.get("panel_id"),
                    "image_job_id": checkpoint.get("image_job_id"),
                    "tool_status": validated_output["status"],
                    "image_call_count": 1,
                    **(trace_attributes or {}),
                },
            ) as span:
                set_span_result(
                    span,
                    {
                        "provider_request_id": validated_output.get(
                            "provider_request_id"
                        ),
                        "error_code": validated_output.get("error_code"),
                    },
                )
        return ToolExecutionResult(
            state=result.state,
            call_step_id=result.call_step_id,
            result_step_id=result.result_step_id,
            output=result.output,
            checkpoint=result.checkpoint,
            replayed=existing_result is not None,
        )
