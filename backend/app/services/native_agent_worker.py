from __future__ import annotations

import asyncio
from datetime import datetime
import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import NativeAgentRun
from app.models.enums import AgentRunStatus
from app.services.native_agent_loop import execute_native_agent_run


logger = logging.getLogger(__name__)

_queue: asyncio.Queue[str] | None = None
_worker_task: asyncio.Task[None] | None = None
_accepting = False


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
        run_id = await _queue.get()
        try:
            await execute_native_agent_run(run_id)
        except asyncio.CancelledError:
            _mark_interrupted_run_failed(
                run_id,
                error_code="NativeAgentWorkerInterrupted",
                error_message="服务停止时本轮仍在执行，请重新提交",
            )
            raise
        except Exception as exc:
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
    await _queue.put(run_id)
    logger.info(
        "native agent run enqueued run_id=%s queue_size=%s",
        run_id,
        _queue.qsize(),
    )


async def recover_native_agent_runs() -> None:
    if _queue is None:
        raise RuntimeError("Native Agent 队列尚未初始化")
    with SessionLocal() as db:
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
            .where(NativeAgentRun.status == AgentRunStatus.queued)
            .order_by(NativeAgentRun.created_at.asc())
        ).all()

    for run_id in interrupted_ids:
        _mark_interrupted_run_failed(
            run_id,
            error_code="NativeAgentProcessInterrupted",
            error_message="服务重启中断了本轮执行；为避免重复生图，本轮未自动重试",
        )
    for run_id in queued_ids:
        await enqueue_native_agent_run(run_id)
    logger.info(
        "native agent recovery complete interrupted_count=%s queued_count=%s",
        len(interrupted_ids),
        len(queued_ids),
    )


async def shutdown_native_agent_queue() -> None:
    global _accepting, _queue, _worker_task
    _accepting = False
    if _worker_task is not None:
        _worker_task.cancel()
        await asyncio.gather(_worker_task, return_exceptions=True)
    _worker_task = None
    _queue = None
    logger.info("native agent queue shutdown complete")
