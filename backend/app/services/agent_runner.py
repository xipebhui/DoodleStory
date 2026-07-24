from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import database
from app.core.config import get_settings
from app.models.entities import AgentConversation, AgentMessage, AgentRun, AgentStep
from app.models.enums import (
    AgentMessageRole,
    AgentRunStatus,
    AgentStepStatus,
    AgentStepType,
)
from app.services.agent_model_router import (
    AgentModelAttemptObserver,
    AgentModelFailure,
    AgentModelResult,
    AgentModelRoute,
    AgentModelRouter,
    AgentModelRoutingError,
)
from app.services.agent_observability import (
    agent_run_span,
    agent_span,
    safe_idempotency_digest,
    set_agent_run_trace_status,
    set_span_result,
    set_span_status,
)
from app.schemas.agent import ComicPlan
from app.services.agent_comic_creation import (
    AgentComicCreationError,
    build_style_context,
    checkpoint_image_tool_results,
    create_comic_task_and_image_tools,
    load_authorized_style,
    style_ref_from_message,
)


logger = logging.getLogger(__name__)
RECOVERABLE_RUN_STATUSES = {
    AgentRunStatus.queued,
    AgentRunStatus.running,
    AgentRunStatus.retrying,
    AgentRunStatus.waiting_for_tool,
}
TERMINAL_RUN_STATUSES = {
    AgentRunStatus.succeeded,
    AgentRunStatus.failed,
    AgentRunStatus.cancelled,
}

_agent_queue: asyncio.Queue[str] | None = None
_agent_worker_tasks: list[asyncio.Task[None]] = []
_active_run_ids: set[str] = set()
_active_run_ids_lock: asyncio.Lock | None = None


class AgentContextLimitExceeded(RuntimeError):
    pass


class AgentCheckpointError(RuntimeError):
    pass


def _next_step_sequence(db: Session, run_id: str) -> int:
    maximum = db.scalar(select(func.max(AgentStep.sequence)).where(AgentStep.run_id == run_id))
    return int(maximum or 0) + 1


def _next_message_sequence(db: Session, conversation_id: str) -> int:
    maximum = db.scalar(
        select(func.max(AgentMessage.sequence)).where(AgentMessage.conversation_id == conversation_id)
    )
    return int(maximum or 0) + 1


def build_agent_input(db: Session, run: AgentRun) -> list[dict[str, Any]]:
    limit = get_settings().agent_context_message_limit
    messages = db.scalars(
        select(AgentMessage)
        .where(
            AgentMessage.conversation_id == run.conversation_id,
            AgentMessage.role.in_([AgentMessageRole.user, AgentMessageRole.assistant]),
        )
        .order_by(AgentMessage.sequence.asc())
        .limit(limit + 1)
    ).all()
    if len(messages) > limit:
        raise AgentContextLimitExceeded(f"会话消息超过 Agent 上下文上限 {limit}，无法安全完整重放")
    if not messages or messages[-1].turn_id != run.turn_id or messages[-1].role != AgentMessageRole.user:
        raise AgentCheckpointError("Run 对应的用户消息不是当前会话最后一条可重放消息")
    return [
        {
            "role": message.role.value,
            "content": message.content,
        }
        for message in messages
    ]


class DatabaseAgentAttemptObserver(AgentModelAttemptObserver):
    def __init__(self, run_id: str, phase: str = "text"):
        self.run_id = run_id
        self.phase = phase
        self.step_ids: dict[tuple[str, int, str | None], str] = {}

    @staticmethod
    def _key(route: AgentModelRoute) -> tuple[str, int, str | None]:
        return route.provider, route.attempt, route.fallback_from

    async def attempt_started(self, route: AgentModelRoute) -> str:
        with database.SessionLocal() as db:
            run = db.get(AgentRun, self.run_id)
            if run is None or run.status in TERMINAL_RUN_STATUSES:
                raise AgentCheckpointError("Agent Run 不存在或已经结束")
            sequence = _next_step_sequence(db, run.id)
            step = AgentStep(
                run_id=run.id,
                sequence=sequence,
                step_type=AgentStepType.model_call,
                status=AgentStepStatus.running,
                provider=route.provider,
                model=route.model,
                api_shape=route.api_shape,
                attempt=route.attempt,
                fallback_from=route.fallback_from,
                fallback_reason=route.fallback_reason,
                input_ref=json.dumps(
                    {
                        "conversation_id": run.conversation_id,
                        "turn_id": run.turn_id,
                        "history_source": "application_database",
                        "uses_previous_response_id": False,
                    },
                    ensure_ascii=False,
                ),
                started_at=datetime.utcnow(),
            )
            run.status = AgentRunStatus.running
            run.current_step_sequence = sequence
            run.model_call_count += 1
            db.add(step)
            db.commit()
            self.step_ids[self._key(route)] = step.id
            logger.info(
                "agent_step_started conversation_id=%s turn_id=%s run_id=%s step_id=%s "
                "provider=%s model=%s api_shape=%s attempt=%s fallback_from=%s",
                run.conversation_id,
                run.turn_id,
                run.id,
                step.id,
                route.provider,
                route.model,
                route.api_shape,
                route.attempt,
                route.fallback_from,
            )
            return step.id

    def _load_step(self, db: Session, route: AgentModelRoute) -> AgentStep:
        step_id = self.step_ids.get(self._key(route))
        step = db.get(AgentStep, step_id) if step_id else None
        if step is None or step.status != AgentStepStatus.running:
            raise AgentCheckpointError("找不到当前运行中的 Agent 模型 Step")
        return step

    async def attempt_succeeded(
        self,
        route: AgentModelRoute,
        result: AgentModelResult,
        latency_ms: int,
    ) -> None:
        with database.SessionLocal() as db:
            step = self._load_step(db, route)
            step.status = AgentStepStatus.succeeded
            step.output_ref = json.dumps(
                {"phase": self.phase, "assistant_content": result.final_output},
                ensure_ascii=False,
            )
            step.usage_json = json.dumps(result.usage, ensure_ascii=False, sort_keys=True)
            step.provider_request_id = result.provider_request_id
            step.latency_ms = latency_ms
            step.finished_at = datetime.utcnow()
            db.commit()
            run = db.get(AgentRun, self.run_id)
            logger.info(
                "agent_step_succeeded conversation_id=%s turn_id=%s run_id=%s step_id=%s "
                "provider=%s latency_ms=%s provider_request_id=%s",
                run.conversation_id if run else None,
                run.turn_id if run else None,
                self.run_id,
                step.id,
                route.provider,
                latency_ms,
                result.provider_request_id,
            )

    async def attempt_failed(
        self,
        route: AgentModelRoute,
        failure: AgentModelFailure,
        latency_ms: int,
    ) -> None:
        with database.SessionLocal() as db:
            step = self._load_step(db, route)
            step.status = AgentStepStatus.failed
            step.error_code = failure.code
            step.error_message = failure.safe_message
            step.internal_error_ref = failure.internal_error_ref
            step.latency_ms = latency_ms
            step.finished_at = datetime.utcnow()
            run = db.get(AgentRun, self.run_id)
            if run is not None:
                run.status = AgentRunStatus.retrying if failure.retryable else AgentRunStatus.running
            db.commit()


def _successful_model_steps(db: Session, run_id: str) -> list[AgentStep]:
    return db.scalars(
        select(AgentStep)
        .where(
            AgentStep.run_id == run_id,
            AgentStep.step_type == AgentStepType.model_call,
            AgentStep.status == AgentStepStatus.succeeded,
        )
        .order_by(AgentStep.sequence.desc())
    ).all()


def _model_step_phase(step: AgentStep) -> str:
    try:
        payload = json.loads(step.output_ref or "")
    except (json.JSONDecodeError, TypeError):
        return "text"
    phase = payload.get("phase")
    return phase if isinstance(phase, str) else "text"


def _successful_model_step(db: Session, run_id: str, phase: str = "text") -> AgentStep | None:
    return next(
        (step for step in _successful_model_steps(db, run_id) if _model_step_phase(step) == phase),
        None,
    )


def _assistant_content_from_step(step: AgentStep) -> str:
    try:
        payload = json.loads(step.output_ref or "")
        content = payload["assistant_content"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AgentCheckpointError("成功模型 Step 的输出 checkpoint 无法读取") from exc
    if not isinstance(content, str) or not content.strip():
        raise AgentCheckpointError("成功模型 Step 没有有效 assistant 内容")
    return content


def finalize_agent_run(run_id: str, assistant_content: str) -> None:
    with agent_span(
        "agent.finalize",
        agent_run_id=run_id,
        span_type="CHAIN",
        attributes={"result_status": "succeeded"},
    ) as span:
        with database.SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if run is None:
                raise AgentCheckpointError("Agent Run 不存在")
            existing_message = db.scalar(
                select(AgentMessage).where(
                    AgentMessage.conversation_id == run.conversation_id,
                    AgentMessage.turn_id == run.turn_id,
                    AgentMessage.role == AgentMessageRole.assistant,
                )
            )
            existing_final = db.scalar(
                select(AgentStep).where(
                    AgentStep.run_id == run.id,
                    AgentStep.step_type == AgentStepType.final,
                    AgentStep.status == AgentStepStatus.succeeded,
                )
            )
            if existing_message is None:
                existing_message = AgentMessage(
                    conversation_id=run.conversation_id,
                    turn_id=run.turn_id,
                    role=AgentMessageRole.assistant,
                    content=assistant_content,
                    sequence=_next_message_sequence(db, run.conversation_id),
                )
                db.add(existing_message)
                db.flush()
            elif existing_message.content != assistant_content:
                raise AgentCheckpointError("同一 Turn 已存在内容不同的 assistant 消息")

            if existing_final is None:
                sequence = _next_step_sequence(db, run.id)
                existing_final = AgentStep(
                    run_id=run.id,
                    sequence=sequence,
                    step_type=AgentStepType.final,
                    status=AgentStepStatus.succeeded,
                    attempt=1,
                    output_ref=json.dumps({"message_id": existing_message.id}, ensure_ascii=False),
                    started_at=datetime.utcnow(),
                    finished_at=datetime.utcnow(),
                )
                db.add(existing_final)
                run.current_step_sequence = sequence
            conversation = db.get(AgentConversation, run.conversation_id)
            if conversation is None:
                raise AgentCheckpointError("Agent Conversation 不存在")
            conversation.last_message_at = datetime.utcnow()
            run.status = AgentRunStatus.succeeded
            run.error_code = None
            run.error_message = None
            run.internal_error_ref = None
            run.finished_at = datetime.utcnow()
            db.commit()
            set_span_result(
                span,
                {
                    "agent_step_id": existing_final.id,
                    "message_id": existing_message.id,
                },
            )


def fail_agent_run(run_id: str, *, code: str, message: str, internal_error_ref: str) -> None:
    with agent_span(
        "agent.finalize",
        agent_run_id=run_id,
        span_type="CHAIN",
        attributes={"result_status": "failed", "error_code": code},
    ) as span:
        set_span_status(span, "ERROR", agent_run_id=run_id)
        with database.SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if run is None or run.status in TERMINAL_RUN_STATUSES:
                return
            run.status = AgentRunStatus.failed
            run.error_code = code
            run.error_message = message
            run.internal_error_ref = internal_error_ref[:120]
            run.finished_at = datetime.utcnow()
            db.commit()


def prepare_agent_run(run_id: str) -> str | None:
    with database.SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        if run is None or run.status in TERMINAL_RUN_STATUSES:
            return None
        successful_step = _successful_model_step(db, run.id, "text")
        if successful_step is not None:
            return _assistant_content_from_step(successful_step)

        interrupted_steps = db.scalars(
            select(AgentStep).where(
                AgentStep.run_id == run.id,
                AgentStep.step_type == AgentStepType.model_call,
                AgentStep.status == AgentStepStatus.running,
            )
        ).all()
        for step in interrupted_steps:
            step.status = AgentStepStatus.failed
            step.error_code = "AgentWorkerInterrupted"
            step.error_message = "服务在安全 checkpoint 之间中断，本次未完成步骤需要重新执行"
            step.internal_error_ref = "AgentWorkerInterrupted"
            step.finished_at = datetime.utcnow()
        run.status = AgentRunStatus.running
        run.started_at = run.started_at or datetime.utcnow()
        run.error_code = None
        run.error_message = None
        run.internal_error_ref = None
        db.commit()
        return None


def _latest_user_message(db: Session, run: AgentRun) -> AgentMessage:
    message = db.scalar(
        select(AgentMessage).where(
            AgentMessage.conversation_id == run.conversation_id,
            AgentMessage.turn_id == run.turn_id,
            AgentMessage.role == AgentMessageRole.user,
        )
    )
    if message is None:
        raise AgentCheckpointError("Agent Run 缺少对应用户消息")
    return message


def _comic_plan_from_checkpoint(db: Session, run_id: str) -> ComicPlan | None:
    step = _successful_model_step(db, run_id, "comic_plan")
    if step is None:
        return None
    return ComicPlan.model_validate_json(_assistant_content_from_step(step))


async def _wait_for_image_tools(run_id: str) -> list[dict[str, object]]:
    started = time.perf_counter()
    wait_metadata_recorded = False
    with agent_span(
        "agent.tool_wait",
        agent_run_id=run_id,
        span_type="CHAIN",
        attributes={"tool_name": "generate_image", "wait_status": "running"},
    ) as span:
        while True:
            with database.SessionLocal() as db:
                run = db.get(AgentRun, run_id)
                if run is None:
                    raise AgentCheckpointError("Agent Run 不存在")
                if run.status in {AgentRunStatus.cancel_requested, AgentRunStatus.cancelled}:
                    raise AgentCheckpointError("Agent Run 已取消")
                if not wait_metadata_recorded:
                    wait_step = db.scalar(
                        select(AgentStep).where(
                            AgentStep.run_id == run.id,
                            AgentStep.step_type == AgentStepType.wait,
                            AgentStep.status == AgentStepStatus.running,
                        )
                    )
                    if wait_step is not None:
                        set_span_result(
                            span,
                            {
                                "agent_step_id": wait_step.id,
                                "idempotency_digest": safe_idempotency_digest(
                                    wait_step.idempotency_key
                                ),
                                "task_id": run.task_id,
                            },
                        )
                    wait_metadata_recorded = True
                outputs = checkpoint_image_tool_results(db, run)
                if outputs is not None:
                    set_span_result(
                        span,
                        {
                            "wait_status": "succeeded",
                            "task_id": run.task_id,
                            "image_job_count": len(outputs),
                            "wait_duration_ms": round(
                                (time.perf_counter() - started) * 1000
                            ),
                            "succeeded_count": sum(
                                output.get("status") == "succeeded" for output in outputs
                            ),
                        },
                    )
                    return outputs
            await asyncio.sleep(1)


async def process_comic_agent_run(
    run_id: str,
    *,
    router: AgentModelRouter,
) -> None:
    with database.SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        if run is None:
            raise AgentCheckpointError("Agent Run 不存在")
        user_message = _latest_user_message(db, run)
        style_ref = style_ref_from_message(user_message)
        if style_ref is None:
            raise AgentCheckpointError("漫画创建 Run 缺少风格资源")
        style = load_authorized_style(db, style_ref.id)
        input_items = build_agent_input(db, run)
        plan = _comic_plan_from_checkpoint(db, run.id)
        final_step = _successful_model_step(db, run.id, "comic_final")
        if final_step is not None:
            finalize_agent_run(run.id, _assistant_content_from_step(final_step))
            return
        style_context = build_style_context(style)

    if plan is None:
        result = await router.run_comic_plan(
            input_items,
            style_context,
            DatabaseAgentAttemptObserver(run_id, "comic_plan"),
        )
        plan = ComicPlan.model_validate(result.structured_output or json.loads(result.final_output))

    with database.SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        if run is None:
            raise AgentCheckpointError("Agent Run 不存在")
        user_message = _latest_user_message(db, run)
        style_ref = style_ref_from_message(user_message)
        if style_ref is None:
            raise AgentCheckpointError("漫画创建 Run 缺少风格资源")
        style = load_authorized_style(db, style_ref.id)
        create_comic_task_and_image_tools(
            db=db,
            run=run,
            user_message=user_message,
            style=style,
            plan=plan,
        )

    tool_outputs = await _wait_for_image_tools(run_id)
    final_context = {
        "title": plan.title,
        "summary": plan.summary,
        "panels": [
            {"panel_key": panel.panel_key, "story_beat": panel.story_beat}
            for panel in plan.panels
        ],
        "tool_outputs": tool_outputs,
    }
    final_input = [
        *input_items,
        {
            "role": "user",
            "content": (
                "以下是应用数据库中已提交的 ComicPlan 与真实 generate_image Tool Output。"
                "请只汇报结果，不要重新规划或生成：\n"
                f"ResultContext={json.dumps(final_context, ensure_ascii=False)}"
            ),
        },
    ]
    result = await router.run_comic_final(
        final_input,
        DatabaseAgentAttemptObserver(run_id, "comic_final"),
    )
    finalize_agent_run(run_id, result.final_output)


async def _claim_run(run_id: str) -> bool:
    global _active_run_ids_lock
    if _active_run_ids_lock is None:
        _active_run_ids_lock = asyncio.Lock()
    async with _active_run_ids_lock:
        if run_id in _active_run_ids:
            return False
        _active_run_ids.add(run_id)
        return True


async def process_agent_run(run_id: str, router: AgentModelRouter | None = None) -> None:
    if not await _claim_run(run_id):
        return
    try:
        with database.SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if run is None or run.status in TERMINAL_RUN_STATUSES:
                return
            trace_context = {
                "conversation_id": run.conversation_id,
                "turn_id": run.turn_id,
                "task_id": run.task_id,
            }
        settings = get_settings()
        with agent_run_span(
            agent_run_id=run_id,
            conversation_id=trace_context["conversation_id"],
            turn_id=trace_context["turn_id"],
            task_id=trace_context["task_id"],
            model=settings.agent_model,
            app_environment=settings.app_env,
        ) as root_span:
            try:
                recovered_output = prepare_agent_run(run_id)
                if recovered_output is not None:
                    finalize_agent_run(run_id, recovered_output)
                    return
                with database.SessionLocal() as db:
                    run = db.get(AgentRun, run_id)
                    if run is None or run.status in TERMINAL_RUN_STATUSES:
                        return
                    user_message = _latest_user_message(db, run)
                    style_ref = style_ref_from_message(user_message)
                    input_items = build_agent_input(db, run)
                model_router = router or AgentModelRouter()
                if style_ref is not None:
                    await process_comic_agent_run(run_id, router=model_router)
                    return
                result = await model_router.run(input_items, DatabaseAgentAttemptObserver(run_id))
                finalize_agent_run(run_id, result.final_output)
            except AgentModelRoutingError as exc:
                fail_agent_run(
                    run_id,
                    code=exc.failure.code,
                    message=exc.failure.safe_message,
                    internal_error_ref=exc.failure.internal_error_ref,
                )
            except AgentContextLimitExceeded as exc:
                fail_agent_run(
                    run_id,
                    code="AgentContextLimitExceeded",
                    message=str(exc),
                    internal_error_ref="AgentContextLimitExceeded",
                )
            except AgentComicCreationError as exc:
                fail_agent_run(
                    run_id,
                    code="AgentComicCreationError",
                    message=str(exc),
                    internal_error_ref="AgentComicCreationError",
                )
            except AgentCheckpointError:
                logger.error("agent_checkpoint_error run_id=%s", run_id)
                fail_agent_run(
                    run_id,
                    code="AgentCheckpointError",
                    message="Agent 运行状态不一致，已停止执行",
                    internal_error_ref="AgentCheckpointError",
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "agent_run_unexpected_error run_id=%s error_type=%s",
                    run_id,
                    type(exc).__name__,
                )
                fail_agent_run(
                    run_id,
                    code="AgentRuntimeError",
                    message="Agent Runtime 执行失败",
                    internal_error_ref=type(exc).__name__,
                )
            finally:
                with database.SessionLocal() as db:
                    completed = db.get(AgentRun, run_id)
                    if completed is not None:
                        set_agent_run_trace_status(
                            root_span,
                            agent_run_id=run_id,
                            run_status=completed.status.value,
                            task_id=completed.task_id,
                            error_code=completed.error_code,
                        )
    finally:
        if _active_run_ids_lock is not None:
            async with _active_run_ids_lock:
                _active_run_ids.discard(run_id)


async def _agent_worker(worker_index: int) -> None:
    assert _agent_queue is not None
    while True:
        run_id = await _agent_queue.get()
        try:
            await process_agent_run(run_id)
        finally:
            _agent_queue.task_done()


def init_agent_queue() -> None:
    global _agent_queue, _agent_worker_tasks, _active_run_ids_lock
    if _agent_queue is not None:
        return
    loop = asyncio.get_running_loop()
    _agent_queue = asyncio.Queue()
    _active_run_ids_lock = asyncio.Lock()
    concurrency = get_settings().agent_worker_concurrency
    _agent_worker_tasks = [
        loop.create_task(_agent_worker(index), name=f"agent-worker-{index}")
        for index in range(concurrency)
    ]


async def enqueue_agent_run(run_id: str) -> None:
    if _agent_queue is None:
        raise RuntimeError("Agent queue has not been initialized")
    await _agent_queue.put(run_id)


async def recover_agent_runs() -> int:
    if _agent_queue is None:
        raise RuntimeError("Agent queue has not been initialized")
    with database.SessionLocal() as db:
        run_ids = db.scalars(
            select(AgentRun.id)
            .where(AgentRun.status.in_(RECOVERABLE_RUN_STATUSES))
            .order_by(AgentRun.updated_at.asc())
        ).all()
    for run_id in run_ids:
        await enqueue_agent_run(run_id)
    return len(run_ids)


async def shutdown_agent_queue() -> None:
    global _agent_queue, _agent_worker_tasks, _active_run_ids_lock
    tasks = list(_agent_worker_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _agent_worker_tasks = []
    _agent_queue = None
    _active_run_ids.clear()
    _active_run_ids_lock = None
