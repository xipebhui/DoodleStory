from __future__ import annotations

import asyncio
from datetime import datetime
import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import NativeAgentRun, NativeAgentStep
from app.models.enums import (
    AgentRunStatus,
    NativeAgentStepStatus,
    NativeAgentStepType,
)
from app.services.native_agent_loop import execute_native_agent_run
from app.services.native_agent_persistence import (
    NativeAgentDatabaseSession,
    NativeAgentRunCancelled,
    NativeAgentStore,
)
from app.services.durable_agent_runtime import (
    claim_current_attempt_for_native_run,
    native_run_id_for_attempt,
    prepared_attempt_id_for_native_run,
    recover_attempts,
    runtime_tables_available,
    workflow_for_native_run,
)


logger = logging.getLogger(__name__)

_queue: asyncio.Queue[tuple[str, str]] | None = None
_worker_task: asyncio.Task[None] | None = None
_accepting = False
_active_run_tasks: dict[str, asyncio.Task[None]] = {}


class NativeAgentRecoveryBlocked(RuntimeError):
    pass


def _mark_interrupted_run_failed(
    run_id: str,
    *,
    error_code: str,
    error_message: str,
) -> None:
    with SessionLocal() as db:
        run = db.scalar(select(NativeAgentRun).where(NativeAgentRun.id == run_id))
        if run is None or run.status in {
            AgentRunStatus.succeeded,
            AgentRunStatus.failed,
            AgentRunStatus.cancel_requested,
            AgentRunStatus.cancelled,
        }:
            return
        run.status = AgentRunStatus.failed
        run.error_code = error_code
        run.error_message = error_message
        run.finished_at = datetime.utcnow()
        db.commit()


async def _worker_loop() -> None:
    if _queue is None:
        raise RuntimeError("Native Agent 队列尚未初始化")
    while True:
        queue_kind, queue_id = await _queue.get()
        try:
            with SessionLocal() as db:
                run_id = (
                    native_run_id_for_attempt(db, attempt_id=queue_id)
                    if queue_kind == "attempt"
                    else queue_id
                )
                if run_id is None:
                    continue
                run = db.get(NativeAgentRun, run_id)
                run_status = run.status if run is not None else None
                durable_enabled = runtime_tables_available(db)
                durable_attempt = (
                    claim_current_attempt_for_native_run(
                        db,
                        native_run_id=run_id,
                        worker_id="native-agent-worker-0",
                    )
                    if durable_enabled
                    else None
                )
            if run_status in {
                AgentRunStatus.cancel_requested,
                AgentRunStatus.cancelled,
            }:
                if run_status == AgentRunStatus.cancel_requested:
                    NativeAgentStore(run_id).cancel_run()
                continue
            if durable_enabled and durable_attempt is None:
                with SessionLocal() as db:
                    if workflow_for_native_run(db, run_id) is not None:
                        logger.info(
                            "native agent run skipped because durable workflow has no ready attempt run_id=%s",
                            run_id,
                        )
                        continue
            run_task = asyncio.create_task(
                execute_native_agent_run(run_id),
                name=f"native-agent-run-{run_id}",
            )
            _active_run_tasks[run_id] = run_task
            try:
                await run_task
            except asyncio.CancelledError:
                current_task = asyncio.current_task()
                if current_task is not None and current_task.cancelling():
                    run_task.cancel()
                    await asyncio.gather(run_task, return_exceptions=True)
                    raise
                NativeAgentStore(run_id).cancel_run()
            finally:
                _active_run_tasks.pop(run_id, None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if isinstance(exc, NativeAgentRunCancelled):
                NativeAgentStore(run_id).cancel_run()
                continue
            logger.exception(
                "native agent worker failed before run terminal state run_id=%s",
                run_id,
            )
            _mark_interrupted_run_failed(
                run_id,
                error_code=type(exc).__name__,
                error_message=str(exc)[:500],
            )
        finally:
            _queue.task_done()


def init_native_agent_queue() -> None:
    global _accepting, _queue, _worker_task
    if _worker_task is not None:
        raise RuntimeError("Native Agent 队列已经初始化")
    _queue = asyncio.Queue()
    _accepting = True
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("native agent queue initialized worker_count=1")


async def enqueue_native_agent_run(run_id: str) -> None:
    if not _accepting or _queue is None:
        raise RuntimeError("Native Agent 队列尚未初始化或正在关闭")
    with SessionLocal() as db:
        durable_attempt_id = (
            prepared_attempt_id_for_native_run(db, native_run_id=run_id)
            if runtime_tables_available(db)
            else None
        )
    if durable_attempt_id:
        await _queue.put(("attempt", durable_attempt_id))
        logger.info(
            "native agent durable attempt enqueued from run_id=%s attempt_id=%s queue_size=%s",
            run_id,
            durable_attempt_id,
            _queue.qsize(),
        )
        return
    await _queue.put(("run", run_id))
    logger.info(
        "native agent run enqueued run_id=%s queue_size=%s",
        run_id,
        _queue.qsize(),
    )


async def enqueue_native_agent_attempt(attempt_id: str) -> None:
    if not _accepting or _queue is None:
        raise RuntimeError("Native Agent 队列尚未初始化或正在关闭")
    await _queue.put(("attempt", attempt_id))
    logger.info(
        "native agent durable attempt enqueued attempt_id=%s queue_size=%s",
        attempt_id,
        _queue.qsize(),
    )


async def cancel_native_agent_run(run_id: str) -> None:
    run_task = _active_run_tasks.get(run_id)
    if run_task is not None:
        run_task.cancel()
        logger.info("native agent active run cancellation signalled run_id=%s", run_id)
        return
    NativeAgentStore(run_id).cancel_run()
    logger.info("native agent queued run cancelled run_id=%s", run_id)


async def recover_native_agent_runs() -> None:
    if _queue is None:
        raise RuntimeError("Native Agent 队列尚未初始化")
    with SessionLocal() as db:
        durable_attempt_ids = recover_attempts(db)
        db.commit()
        interrupted_ids = db.scalars(
            select(NativeAgentRun.id).where(
                NativeAgentRun.status.in_(
                    [
                        AgentRunStatus.running,
                        AgentRunStatus.waiting_for_tool,
                    ]
                )
            )
        ).all()
        queued_ids = db.scalars(
            select(NativeAgentRun.id)
            .where(
                NativeAgentRun.status.in_(
                    [
                        AgentRunStatus.queued,
                        AgentRunStatus.retrying,
                    ]
                )
            )
            .order_by(NativeAgentRun.created_at.asc())
        ).all()
        cancel_requested_ids = db.scalars(
            select(NativeAgentRun.id).where(
                NativeAgentRun.status == AgentRunStatus.cancel_requested
            )
        ).all()

    recovered_count = 0
    blocked_count = 0
    for run_id in cancel_requested_ids:
        NativeAgentStore(run_id).cancel_run()
    for run_id in interrupted_ids:
        sdk_session = NativeAgentDatabaseSession(
            run_id,
            session_factory=SessionLocal,
        )
        store = NativeAgentStore(run_id, session_factory=SessionLocal)
        with SessionLocal() as db:
            tool_steps = db.scalars(
                select(NativeAgentStep)
                .where(
                    NativeAgentStep.run_id == run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.tool_call,
                )
                .order_by(NativeAgentStep.sequence.asc())
            ).all()
        blocked_step: NativeAgentStep | None = None
        for step in tool_steps:
            if step.status in {
                NativeAgentStepStatus.prepared,
                NativeAgentStepStatus.running,
                NativeAgentStepStatus.failed,
                NativeAgentStepStatus.unknown,
            }:
                blocked_step = step
                break
            if (
                step.status == NativeAgentStepStatus.succeeded
                and step.tool_call_id
                and not await sdk_session.has_tool_output(step.tool_call_id)
            ):
                blocked_step = step
                break
        if blocked_step is not None:
            message = (
                "服务中断时 generate_image 的 Provider 结果或 SDK Tool Output "
                "无法同时确认；为避免重复生图，本轮不会自动恢复"
            )
            store.mark_step_unknown(blocked_step.id, message)
            store.fail_run(NativeAgentRecoveryBlocked(message))
            blocked_count += 1
            continue
        with SessionLocal() as db:
            model_steps = db.scalars(
                select(NativeAgentStep).where(
                    NativeAgentStep.run_id == run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.model_call,
                    NativeAgentStep.status == NativeAgentStepStatus.running,
                )
            ).all()
            for step in model_steps:
                step.status = NativeAgentStepStatus.unknown
                step.error_code = "NativeAgentModelInterrupted"
                step.error_message = "模型调用被服务重启中断，将从已保存 SDK 上下文继续"
                step.finished_at = datetime.utcnow()
            run = db.get(NativeAgentRun, run_id)
            if run is not None:
                run.status = AgentRunStatus.queued
                run.error_code = None
                run.error_message = None
                run.finished_at = None
            db.commit()
        store.append_event(
            "run.recovery_queued",
            {"status": AgentRunStatus.queued.value},
        )
        await enqueue_native_agent_run(run_id)
        recovered_count += 1
    for run_id in queued_ids:
        await enqueue_native_agent_run(run_id)
    logger.info(
        "native agent recovery complete interrupted_count=%s recovered_count=%s "
        "blocked_count=%s queued_count=%s durable_attempt_count=%s",
        len(interrupted_ids),
        recovered_count,
        blocked_count,
        len(queued_ids),
        len(durable_attempt_ids),
    )


async def shutdown_native_agent_queue() -> None:
    global _accepting, _queue, _worker_task
    _accepting = False
    if _worker_task is not None:
        _worker_task.cancel()
        await asyncio.gather(_worker_task, return_exceptions=True)
    _active_run_tasks.clear()
    _worker_task = None
    _queue = None
    logger.info("native agent queue shutdown complete")
