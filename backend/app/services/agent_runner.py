from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
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


logger = logging.getLogger(__name__)
RECOVERABLE_RUN_STATUSES = {
    AgentRunStatus.queued,
    AgentRunStatus.running,
    AgentRunStatus.retrying,
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
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.step_ids: dict[tuple[str, int, str | None], str] = {}

    @staticmethod
    def _key(route: AgentModelRoute) -> tuple[str, int, str | None]:
        return route.provider, route.attempt, route.fallback_from

    async def attempt_started(self, route: AgentModelRoute) -> None:
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
                {"assistant_content": result.final_output},
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


def _successful_model_step(db: Session, run_id: str) -> AgentStep | None:
    return db.scalar(
        select(AgentStep)
        .where(
            AgentStep.run_id == run_id,
            AgentStep.step_type == AgentStepType.model_call,
            AgentStep.status == AgentStepStatus.succeeded,
        )
        .order_by(AgentStep.sequence.desc())
        .limit(1)
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


def fail_agent_run(run_id: str, *, code: str, message: str, internal_error_ref: str) -> None:
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
        successful_step = _successful_model_step(db, run.id)
        if successful_step is not None:
            return _assistant_content_from_step(successful_step)

        interrupted_steps = db.scalars(
            select(AgentStep).where(
                AgentStep.run_id == run.id,
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
        recovered_output = prepare_agent_run(run_id)
        if recovered_output is not None:
            finalize_agent_run(run_id, recovered_output)
            return
        with database.SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if run is None or run.status in TERMINAL_RUN_STATUSES:
                return
            input_items = build_agent_input(db, run)
        model_router = router or AgentModelRouter()
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
    except AgentCheckpointError:
        logger.error("agent_checkpoint_error run_id=%s", run_id)
        fail_agent_run(
            run_id,
            code="AgentCheckpointError",
            message="Agent 运行状态不一致，已停止执行",
            internal_error_ref="AgentCheckpointError",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("agent_run_unexpected_error run_id=%s error_type=%s", run_id, type(exc).__name__)
        fail_agent_run(
            run_id,
            code="AgentRuntimeError",
            message="Agent Runtime 执行失败",
            internal_error_ref=type(exc).__name__,
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
