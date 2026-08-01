from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from agents.items import TResponseInputItem
from agents.memory.session import SessionABC
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker, selectinload

from app.core.database import SessionLocal
from app.models.entities import (
    FileAsset,
    NativeAgentAudio,
    NativeAgentContextItem,
    NativeAgentEvent,
    NativeAgentExternalContent,
    NativeAgentImage,
    NativeAgentItem,
    NativeAgentRun,
    NativeAgentStep,
    NativeAgentSubtitle,
    NativeAgentVideo,
)
from app.models.enums import (
    AgentRunStatus,
    FileAssetPurpose,
    NativeAgentItemType,
    NativeAgentStepStatus,
    NativeAgentStepType,
)
from app.services.image_generation import GeneratedImageFile
from app.services.remotion_video import GeneratedRemotionVideo
from app.services.storage import save_binary_file
from app.services.volcengine_speech import GeneratedSpeech
from app.services.whisper_subtitles import GeneratedSubtitles


class NativeAgentRunCancelled(RuntimeError):
    pass


class NativeAgentRetryArgumentsMismatch(RuntimeError):
    pass


def _require_run_writable(run: NativeAgentRun) -> None:
    if run.status in {
        AgentRunStatus.cancel_requested,
        AgentRunStatus.cancelled,
    }:
        raise NativeAgentRunCancelled("Native Agent Run 已请求取消")


def _json_default(value: object) -> object:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _json_dumps(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    )


def _next_sequence(
    db: Session,
    model: type[NativeAgentItem]
    | type[NativeAgentStep]
    | type[NativeAgentContextItem],
    run_id: str,
) -> int:
    latest = db.scalar(select(func.max(model.sequence)).where(model.run_id == run_id))
    return int(latest or 0) + 1


def add_native_agent_event(
    db: Session,
    run_id: str,
    event_type: str,
    payload: dict[str, object],
) -> NativeAgentEvent:
    sequence = db.scalar(
        update(NativeAgentRun)
        .where(NativeAgentRun.id == run_id)
        .values(event_sequence=NativeAgentRun.event_sequence + 1)
        .returning(NativeAgentRun.event_sequence)
    )
    if sequence is None:
        raise RuntimeError("Native Agent Run 不存在，无法追加事件")
    event = NativeAgentEvent(
        run_id=run_id,
        sequence=int(sequence),
        event_type=event_type,
        payload_json=_json_dumps(payload),
    )
    db.add(event)
    db.flush()
    return event


_add_event = add_native_agent_event


@dataclass(frozen=True)
class CompletedNativeTool:
    step_id: str
    image_id: str
    asset_id: str
    storage_backend: object
    storage_key: str
    public_url: str | None
    content_type: str
    width: int | None
    height: int | None
    provider_request_id: str | None


@dataclass(frozen=True)
class CompletedNativeImageInspection:
    step_id: str
    image_id: str
    verdict: str
    scores: dict[str, float]
    issues: list[dict[str, object]]
    provider: str
    model: str
    latency_ms: int


@dataclass(frozen=True)
class CompletedNativeSpeech:
    step_id: str
    audio_id: str
    asset_id: str
    text: str
    content_type: str
    byte_size: int
    response_format: str
    sample_rate: int
    duration_ms: int | None
    speed: float
    speech_rate: int
    provider_request_id: str | None


@dataclass(frozen=True)
class CompletedNativeSubtitle:
    step_id: str
    subtitle_id: str
    audio_id: str
    asset_id: str
    content_type: str
    byte_size: int
    text: str
    language: str
    model: str
    duration_ms: int
    cues: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class CompletedNativeVideo:
    step_id: str
    video_id: str
    asset_id: str
    content_type: str
    byte_size: int
    template_id: str
    renderer_version: str
    duration_ms: int
    duration_in_frames: int
    fps: int
    width: int
    height: int
    bgm_asset_id: str | None


@dataclass(frozen=True)
class CompletedNativeExternalContent:
    step_id: str
    external_content_id: str
    asset_id: str
    platform: str
    title: str | None
    author_name: str | None
    publish_time: str | None
    source_url: str
    excerpt: str
    byte_size: int


class NativeAgentDatabaseSession(SessionABC):
    """Agents SDK Session backed by the application's Native Agent database."""

    session_settings = None

    def __init__(
        self,
        run_id: str,
        *,
        session_factory: sessionmaker = SessionLocal,
    ) -> None:
        self.session_id = run_id
        self._session_factory = session_factory

    async def get_items(self, limit: int | None = None) -> list[TResponseInputItem]:
        with self._session_factory() as db:
            query = (
                select(NativeAgentContextItem)
                .where(NativeAgentContextItem.run_id == self.session_id)
                .order_by(NativeAgentContextItem.sequence.asc())
            )
            rows = list(db.scalars(query).all())
        if limit is not None:
            rows = rows[-limit:]
        return [json.loads(row.item_json) for row in rows]

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        if not items:
            return
        with self._session_factory() as db:
            sequence = _next_sequence(
                db,
                NativeAgentContextItem,
                self.session_id,
            )
            for item in items:
                db.add(
                    NativeAgentContextItem(
                        run_id=self.session_id,
                        sequence=sequence,
                        item_json=_json_dumps(item),
                    )
                )
                sequence += 1
            db.commit()

    async def pop_item(self) -> TResponseInputItem | None:
        with self._session_factory() as db:
            row = db.scalar(
                select(NativeAgentContextItem)
                .where(NativeAgentContextItem.run_id == self.session_id)
                .order_by(NativeAgentContextItem.sequence.desc())
                .limit(1)
            )
            if row is None:
                return None
            value = json.loads(row.item_json)
            db.delete(row)
            db.commit()
            return value

    async def clear_session(self) -> None:
        with self._session_factory() as db:
            db.execute(
                delete(NativeAgentContextItem).where(
                    NativeAgentContextItem.run_id == self.session_id
                )
            )
            db.commit()

    async def has_items(self) -> bool:
        with self._session_factory() as db:
            return bool(
                db.scalar(
                    select(func.count(NativeAgentContextItem.id)).where(
                        NativeAgentContextItem.run_id == self.session_id
                    )
                )
            )

    async def has_tool_output(self, tool_call_id: str) -> bool:
        for item in await self.get_items():
            if (
                isinstance(item, dict)
                and item.get("type") == "function_call_output"
                and item.get("call_id") == tool_call_id
            ):
                return True
        return False


class NativeAgentStore:
    def __init__(
        self,
        run_id: str,
        *,
        session_factory: sessionmaker = SessionLocal,
    ) -> None:
        self.run_id = run_id
        self._session_factory = session_factory

    @property
    def session_factory(self) -> sessionmaker:
        return self._session_factory

    def append_event(
        self,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        with self._session_factory() as db:
            _add_event(db, self.run_id, event_type, payload)
            db.commit()

    def request_retry(self, *, failed_step_id: str | None) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            if run.status in {
                AgentRunStatus.queued,
                AgentRunStatus.running,
                AgentRunStatus.waiting_for_tool,
                AgentRunStatus.retrying,
                AgentRunStatus.cancel_requested,
            }:
                raise RuntimeError("Native Agent Run 正在执行，不能重复提交重试")
            if run.status == AgentRunStatus.cancelled:
                raise RuntimeError("用户已终止的 Native Agent Run 不能自动重试")

            retry_step: NativeAgentStep | None = None
            if failed_step_id is not None:
                retry_step = db.get(NativeAgentStep, failed_step_id)
                if (
                    retry_step is None
                    or retry_step.run_id != self.run_id
                    or retry_step.step_type != NativeAgentStepType.tool_call
                    or retry_step.status != NativeAgentStepStatus.failed
                ):
                    raise RuntimeError("Native Agent 重试目标不是已知失败的 Tool Step")
                retry_step.status = NativeAgentStepStatus.prepared
                retry_step.started_at = None
                retry_step.finished_at = None
                retry_step.error_code = None
                retry_step.error_message = None

            run.status = AgentRunStatus.retrying
            run.error_code = None
            run.error_message = None
            run.final_output = None
            run.finished_at = None
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.user_input,
                    payload_json=_json_dumps(
                        {"content": "重试", "control": "retry"}
                    ),
                )
            )
            db.add(
                NativeAgentContextItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(
                        db,
                        NativeAgentContextItem,
                        self.run_id,
                    ),
                    item_json=_json_dumps(
                        {
                            "role": "user",
                            "content": (
                                "重试。请从最近失败的 Tool 继续，严格复用失败调用的"
                                "原参数和已经成功生成的资产，不要重新执行已经成功的付费 Tool。"
                            ),
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "run.retry_requested",
                {
                    "status": AgentRunStatus.retrying.value,
                    "failed_step_id": retry_step.id if retry_step else None,
                    "failed_step_sequence": (
                        retry_step.sequence if retry_step else None
                    ),
                    "tool": retry_step.name if retry_step else None,
                },
            )
            db.commit()

    def _claim_retry_step(
        self,
        db: Session,
        *,
        name: str,
        tool_call_id: str,
        idempotency_key: str,
        arguments: dict[str, object],
    ) -> NativeAgentStep | None:
        retry_step = db.scalar(
            select(NativeAgentStep)
            .where(
                NativeAgentStep.run_id == self.run_id,
                NativeAgentStep.step_type == NativeAgentStepType.tool_call,
                NativeAgentStep.status == NativeAgentStepStatus.prepared,
                NativeAgentStep.attempts > 0,
            )
            .order_by(NativeAgentStep.sequence.desc())
            .limit(1)
        )
        if retry_step is None:
            return None
        arguments_json = _json_dumps(arguments)
        if (
            retry_step.name != name
            or retry_step.input_summary_json != arguments_json
        ):
            raise NativeAgentRetryArgumentsMismatch(
                "重试必须先使用最近失败 Tool 的原名称和原参数"
            )
        retry_step.tool_call_id = tool_call_id
        retry_step.idempotency_key = idempotency_key
        retry_step.error_code = None
        retry_step.error_message = None
        db.add(
            NativeAgentItem(
                run_id=self.run_id,
                sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                item_type=NativeAgentItemType.tool_call,
                payload_json=_json_dumps(
                    {
                        "tool": name,
                        "tool_call_id": tool_call_id,
                        "step_id": retry_step.id,
                        **arguments,
                    }
                ),
            )
        )
        _add_event(
            db,
            self.run_id,
            "tool.retry_prepared",
            {
                "step_sequence": retry_step.sequence,
                "tool": name,
                "tool_call_id": tool_call_id,
                "arguments": arguments,
                "next_attempt": retry_step.attempts + 1,
            },
        )
        db.commit()
        db.refresh(retry_step)
        return retry_step

    def start_run(self, *, resumed: bool) -> int:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            run.status = AgentRunStatus.running
            if run.started_at is None:
                run.started_at = datetime.utcnow()
            run.error_code = None
            run.error_message = None
            run.finished_at = None
            event_type = "run.resumed" if resumed else "run.started"
            execution_attempt = int(
                db.scalar(
                    select(func.count(NativeAgentEvent.id)).where(
                        NativeAgentEvent.run_id == self.run_id,
                        NativeAgentEvent.event_type.in_(
                            ("run.started", "run.resumed")
                        ),
                    )
                )
                or 0
            ) + 1
            _add_event(
                db,
                self.run_id,
                event_type,
                {
                    "status": "running",
                    "execution_attempt": execution_attempt,
                },
            )
            db.commit()
            return execution_attempt

    def record_model_request_started(
        self,
        *,
        metric_call_id: str,
        role: str,
        phase: str,
    ) -> int:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            model_call_count = db.scalar(
                update(NativeAgentRun)
                .where(NativeAgentRun.id == self.run_id)
                .values(
                    model_call_count=NativeAgentRun.model_call_count + 1
                )
                .returning(NativeAgentRun.model_call_count)
            )
            if model_call_count is None:
                raise RuntimeError("Native Agent Run 不存在")
            _add_event(
                db,
                self.run_id,
                "model.request.started",
                {
                    "metric_call_id": metric_call_id,
                    "role": role,
                    "phase": phase,
                    "model_call_count": int(model_call_count),
                },
            )
            db.commit()
            return int(model_call_count)

    def record_model_request_completed(
        self,
        *,
        metric_call_id: str,
        role: str,
        phase: str,
        usage: dict[str, object] | None,
    ) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            _add_event(
                db,
                self.run_id,
                "model.request.completed",
                {
                    "metric_call_id": metric_call_id,
                    "role": role,
                    "phase": phase,
                    "usage": usage,
                },
            )
            db.commit()

    def start_model_step(self, response_id: str) -> NativeAgentStep:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            previous = db.scalar(
                select(NativeAgentStep)
                .where(
                    NativeAgentStep.run_id == self.run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.model_call,
                    NativeAgentStep.status == NativeAgentStepStatus.succeeded,
                )
                .order_by(NativeAgentStep.sequence.desc())
                .limit(1)
            )
            if previous is not None:
                _add_event(
                    db,
                    self.run_id,
                    "checkpoint.saved",
                    {"through_step_sequence": previous.sequence},
                )
            step = NativeAgentStep(
                run_id=self.run_id,
                sequence=_next_sequence(db, NativeAgentStep, self.run_id),
                step_type=NativeAgentStepType.model_call,
                status=NativeAgentStepStatus.running,
                name="model",
                idempotency_key=f"native:{self.run_id}:model:{response_id}",
                output_ref_json=_json_dumps({"response_id": response_id}),
                attempts=1,
                started_at=datetime.utcnow(),
            )
            db.add(step)
            response_sequence = int(
                db.scalar(
                    select(func.count(NativeAgentStep.id)).where(
                        NativeAgentStep.run_id == self.run_id,
                        NativeAgentStep.step_type
                        == NativeAgentStepType.model_call,
                    )
                )
                or 0
            ) + 1
            _add_event(
                db,
                self.run_id,
                "response.started",
                {
                    "step_sequence": step.sequence,
                    "response_id": response_id,
                    "model_call_count": response_sequence,
                },
            )
            db.commit()
            db.refresh(step)
            return step

    def complete_model_step(
        self,
        response_id: str,
        *,
        usage: dict[str, object] | None,
    ) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            step = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.run_id == self.run_id,
                    NativeAgentStep.idempotency_key
                    == f"native:{self.run_id}:model:{response_id}",
                )
            )
            if step is None:
                raise RuntimeError("Native Agent 模型 Step 不存在")
            step.status = NativeAgentStepStatus.succeeded
            step.finished_at = datetime.utcnow()
            step.output_ref_json = _json_dumps(
                {"response_id": response_id, "usage": usage or {}}
            )
            _add_event(
                db,
                self.run_id,
                "response.completed",
                {
                    "step_sequence": step.sequence,
                    "response_id": response_id,
                    "usage": usage or {},
                },
            )
            db.commit()

    def fail_active_model_step(self, exc: Exception) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is not None and run.status in {
                AgentRunStatus.cancel_requested,
                AgentRunStatus.cancelled,
            }:
                return
            step = db.scalar(
                select(NativeAgentStep)
                .where(
                    NativeAgentStep.run_id == self.run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.model_call,
                    NativeAgentStep.status == NativeAgentStepStatus.running,
                )
                .order_by(NativeAgentStep.sequence.desc())
                .limit(1)
            )
            if step is None:
                return
            step.status = NativeAgentStepStatus.failed
            step.finished_at = datetime.utcnow()
            step.error_code = type(exc).__name__
            step.error_message = str(exc)[:500]
            db.commit()

    def append_response_text_delta(self, response_id: str, delta: str) -> None:
        self.append_event(
            "response.output_text.delta",
            {"response_id": response_id, "delta": delta},
        )

    def start_function_call(
        self,
        *,
        response_id: str,
        item_id: str,
        tool_call_id: str,
        name: str,
        output_index: int,
    ) -> None:
        self.append_event(
            "response.function_call.started",
            {
                "response_id": response_id,
                "item_id": item_id,
                "tool_call_id": tool_call_id,
                "name": name,
                "output_index": output_index,
            },
        )

    def append_function_call_arguments_delta(
        self,
        *,
        response_id: str,
        item_id: str,
        tool_call_id: str,
        name: str,
        delta: str,
    ) -> None:
        self.append_event(
            "response.function_call.arguments.delta",
            {
                "response_id": response_id,
                "item_id": item_id,
                "tool_call_id": tool_call_id,
                "name": name,
                "delta": delta,
            },
        )

    def complete_function_call_arguments(
        self,
        *,
        response_id: str,
        item_id: str,
        tool_call_id: str,
        name: str,
        arguments: str,
    ) -> None:
        self.append_event(
            "response.function_call.arguments.done",
            {
                "response_id": response_id,
                "item_id": item_id,
                "tool_call_id": tool_call_id,
                "name": name,
                "arguments": arguments,
            },
        )

    def prepare_tool(
        self,
        *,
        tool_call_id: str,
        prompt: str,
        provider: str,
    ) -> CompletedNativeTool | NativeAgentStep:
        idempotency_key = (
            f"native:{self.run_id}:generate_image:{tool_call_id}"
        )
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            arguments = {"prompt": prompt, "provider": provider}
            retry_step = self._claim_retry_step(
                db,
                name="generate_image",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                arguments=arguments,
            )
            if retry_step is not None:
                return retry_step
            existing = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.status == NativeAgentStepStatus.succeeded:
                    return self._completed_tool(db, existing)
                raise RuntimeError(
                    "同一 generate_image 调用已存在未确认执行，拒绝重复调用"
                )
            step = NativeAgentStep(
                run_id=self.run_id,
                sequence=_next_sequence(db, NativeAgentStep, self.run_id),
                step_type=NativeAgentStepType.tool_call,
                status=NativeAgentStepStatus.prepared,
                name="generate_image",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                input_summary_json=_json_dumps(arguments),
                attempts=0,
            )
            db.add(step)
            db.flush()
            from app.services.durable_agent_runtime import (
                prepare_native_image_effect,
            )

            prepare_native_image_effect(
                db,
                native_run_id=self.run_id,
                native_step=step,
            )
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_call,
                    payload_json=_json_dumps(
                        {
                            "tool": "generate_image",
                            "prompt": prompt,
                            "provider": provider,
                            "tool_call_id": tool_call_id,
                            "step_id": step.id,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.prepared",
                {
                    "step_sequence": step.sequence,
                    "tool": "generate_image",
                    "tool_call_id": tool_call_id,
                    "arguments": arguments,
                },
            )
            db.commit()
            db.refresh(step)
            return step

    def prepare_speech_tool(
        self,
        *,
        tool_call_id: str,
        text: str,
        speed: float,
    ) -> CompletedNativeSpeech | NativeAgentStep:
        idempotency_key = f"native:{self.run_id}:generate_speech:{tool_call_id}"
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            arguments = {"text": text, "speed": speed}
            retry_step = self._claim_retry_step(
                db,
                name="generate_speech",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                arguments=arguments,
            )
            if retry_step is not None:
                return retry_step
            existing = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.status == NativeAgentStepStatus.succeeded:
                    return self._completed_speech(db, existing)
                raise RuntimeError(
                    "同一 generate_speech 调用已存在未确认执行，拒绝重复调用"
                )
            reusable_audio = db.scalar(
                select(NativeAgentAudio)
                .where(
                    NativeAgentAudio.run_id == self.run_id,
                    NativeAgentAudio.text == text,
                    NativeAgentAudio.speed_snapshot == float(speed),
                )
                .order_by(NativeAgentAudio.created_at.asc())
                .limit(1)
            )
            if reusable_audio is not None:
                reusable_step = db.scalar(
                    select(NativeAgentStep)
                    .where(
                        NativeAgentStep.run_id == self.run_id,
                        NativeAgentStep.name == "generate_speech",
                        NativeAgentStep.status == NativeAgentStepStatus.succeeded,
                        NativeAgentStep.output_ref_json.contains(reusable_audio.id),
                    )
                    .order_by(NativeAgentStep.sequence.asc())
                    .limit(1)
                )
                if reusable_step is None:
                    raise RuntimeError("可复用语音缺少成功 Tool Step")
                return self._completed_speech(db, reusable_step)
            step = NativeAgentStep(
                run_id=self.run_id,
                sequence=_next_sequence(db, NativeAgentStep, self.run_id),
                step_type=NativeAgentStepType.tool_call,
                status=NativeAgentStepStatus.prepared,
                name="generate_speech",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                input_summary_json=_json_dumps(arguments),
                attempts=0,
            )
            db.add(step)
            db.flush()
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_call,
                    payload_json=_json_dumps(
                        {
                            "tool": "generate_speech",
                            "text": text,
                            "speed": speed,
                            "tool_call_id": tool_call_id,
                            "step_id": step.id,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.prepared",
                {
                    "step_sequence": step.sequence,
                    "tool": "generate_speech",
                    "tool_call_id": tool_call_id,
                    "arguments": {"text": text, "speed": speed},
                },
            )
            db.commit()
            db.refresh(step)
            return step

    def prepare_image_inspection_tool(
        self,
        *,
        tool_call_id: str,
        image_id: str,
        checks: list[str],
        expected: dict[str, object],
    ) -> CompletedNativeImageInspection | NativeAgentStep:
        idempotency_key = f"native:{self.run_id}:inspect_image:{tool_call_id}"
        arguments = {
            "image_id": image_id,
            "checks": checks,
            "expected": expected,
        }
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            image = db.get(NativeAgentImage, image_id)
            if image is None or image.run_id != self.run_id:
                raise RuntimeError("image_id 不属于当前 Run")
            existing = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.status == NativeAgentStepStatus.succeeded:
                    return self._completed_image_inspection(existing)
                raise RuntimeError("同一 inspect_image 调用已存在未确认执行，拒绝重复调用")
            prior = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.run_id == self.run_id,
                    NativeAgentStep.name == "inspect_image",
                    NativeAgentStep.status == NativeAgentStepStatus.succeeded,
                    NativeAgentStep.output_ref_json.contains(image_id),
                )
            )
            if prior is not None:
                return self._completed_image_inspection(prior)
            step = NativeAgentStep(
                run_id=self.run_id,
                sequence=_next_sequence(db, NativeAgentStep, self.run_id),
                step_type=NativeAgentStepType.tool_call,
                status=NativeAgentStepStatus.prepared,
                name="inspect_image",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                input_summary_json=_json_dumps(arguments),
                attempts=0,
            )
            db.add(step)
            db.flush()
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_call,
                    payload_json=_json_dumps(
                        {
                            "tool": "inspect_image",
                            "tool_call_id": tool_call_id,
                            "step_id": step.id,
                            **arguments,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.prepared",
                {
                    "step_sequence": step.sequence,
                    "tool": "inspect_image",
                    "tool_call_id": tool_call_id,
                    "arguments": arguments,
                },
            )
            db.commit()
            db.refresh(step)
            return step

    def prepare_subtitle_tool(
        self,
        *,
        tool_call_id: str,
        audio_id: str,
    ) -> CompletedNativeSubtitle | NativeAgentStep:
        idempotency_key = f"native:{self.run_id}:generate_subtitles:{tool_call_id}"
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            failed_attempts = (
                db.scalar(
                    select(func.count(NativeAgentStep.id)).where(
                        NativeAgentStep.run_id == self.run_id,
                        NativeAgentStep.name == "generate_subtitles",
                        NativeAgentStep.status == NativeAgentStepStatus.failed,
                        NativeAgentStep.input_summary_json.contains(audio_id),
                    )
                )
                or 0
            )
            if failed_attempts >= 2:
                raise RuntimeError("同一音频的字幕生成已失败 2 次，拒绝继续自动重试")
            arguments = {"audio_id": audio_id}
            retry_step = self._claim_retry_step(
                db,
                name="generate_subtitles",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                arguments=arguments,
            )
            if retry_step is not None:
                return retry_step
            existing = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.status == NativeAgentStepStatus.succeeded:
                    return self._completed_subtitle(db, existing)
                raise RuntimeError(
                    "同一 generate_subtitles 调用已存在未确认执行，拒绝重复调用"
                )
            step = NativeAgentStep(
                run_id=self.run_id,
                sequence=_next_sequence(db, NativeAgentStep, self.run_id),
                step_type=NativeAgentStepType.tool_call,
                status=NativeAgentStepStatus.prepared,
                name="generate_subtitles",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                input_summary_json=_json_dumps(arguments),
                attempts=0,
            )
            db.add(step)
            db.flush()
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_call,
                    payload_json=_json_dumps(
                        {
                            "tool": "generate_subtitles",
                            "tool_call_id": tool_call_id,
                            "step_id": step.id,
                            **arguments,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.prepared",
                {
                    "step_sequence": step.sequence,
                    "tool": "generate_subtitles",
                    "tool_call_id": tool_call_id,
                    "arguments": arguments,
                },
            )
            db.commit()
            db.refresh(step)
            return step

    def prepare_video_tool(
        self,
        *,
        tool_call_id: str,
        scenes: list[dict[str, object]],
        bgm_asset_id: str | None,
    ) -> CompletedNativeVideo | NativeAgentStep:
        idempotency_key = (
            f"native:{self.run_id}:render_story_video:{tool_call_id}"
        )
        arguments = {
            "scenes": scenes,
            "bgm_asset_id": bgm_asset_id,
        }
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            retry_step = self._claim_retry_step(
                db,
                name="render_story_video",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                arguments=arguments,
            )
            if retry_step is not None:
                return retry_step
            existing = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.status == NativeAgentStepStatus.succeeded:
                    return self._completed_video(db, existing)
                raise RuntimeError(
                    "同一 render_story_video 调用已存在未确认执行，拒绝重复调用"
                )
            step = NativeAgentStep(
                run_id=self.run_id,
                sequence=_next_sequence(db, NativeAgentStep, self.run_id),
                step_type=NativeAgentStepType.tool_call,
                status=NativeAgentStepStatus.prepared,
                name="render_story_video",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                input_summary_json=_json_dumps(arguments),
                attempts=0,
            )
            db.add(step)
            db.flush()
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_call,
                    payload_json=_json_dumps(
                        {
                            "tool": "render_story_video",
                            "tool_call_id": tool_call_id,
                            "step_id": step.id,
                            **arguments,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.prepared",
                {
                    "step_sequence": step.sequence,
                    "tool": "render_story_video",
                    "tool_call_id": tool_call_id,
                    "arguments": arguments,
                },
            )
            db.commit()
            db.refresh(step)
            return step

    def prepare_external_content_tool(
        self,
        *,
        tool_call_id: str,
        url: str,
    ) -> CompletedNativeExternalContent | NativeAgentStep:
        idempotency_key = (
            f"native:{self.run_id}:capture_wechat_article:{tool_call_id}"
        )
        arguments = {"url": url}
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            retry_step = self._claim_retry_step(
                db,
                name="capture_wechat_article",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                arguments=arguments,
            )
            if retry_step is not None:
                return retry_step
            existing = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.status == NativeAgentStepStatus.succeeded:
                    return self._completed_external_content(db, existing)
                raise RuntimeError(
                    "同一 capture_wechat_article 调用已存在未确认执行，拒绝重复调用"
                )
            step = NativeAgentStep(
                run_id=self.run_id,
                sequence=_next_sequence(db, NativeAgentStep, self.run_id),
                step_type=NativeAgentStepType.tool_call,
                status=NativeAgentStepStatus.prepared,
                name="capture_wechat_article",
                tool_call_id=tool_call_id,
                idempotency_key=idempotency_key,
                input_summary_json=_json_dumps(arguments),
                attempts=0,
            )
            db.add(step)
            db.flush()
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_call,
                    payload_json=_json_dumps(
                        {
                            "tool": "capture_wechat_article",
                            "tool_call_id": tool_call_id,
                            "step_id": step.id,
                            **arguments,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.prepared",
                {
                    "step_sequence": step.sequence,
                    "tool": "capture_wechat_article",
                    "tool_call_id": tool_call_id,
                    "arguments": arguments,
                },
            )
            db.commit()
            db.refresh(step)
            return step

    def start_tool(self, step_id: str) -> None:
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            run = db.get(NativeAgentRun, self.run_id)
            if step is None or run is None:
                raise RuntimeError("Native Agent Tool Step 或 Run 不存在")
            _require_run_writable(run)
            if step.status != NativeAgentStepStatus.prepared:
                raise RuntimeError("Native Agent Tool Step 不是 prepared 状态")
            step.status = NativeAgentStepStatus.running
            step.attempts += 1
            step.started_at = datetime.utcnow()
            _add_event(
                db,
                self.run_id,
                "tool.started",
                {
                    "step_sequence": step.sequence,
                    "tool": step.name,
                    "tool_call_id": step.tool_call_id,
                    "attempt": step.attempts,
                },
            )
            from app.services.durable_agent_runtime import (
                update_native_image_effect,
            )

            update_native_image_effect(
                db,
                native_step_id=step.id,
                status="submitted",
            )
            db.commit()

    def complete_tool(
        self,
        step_id: str,
        *,
        prompt: str,
        generated: GeneratedImageFile,
        image_model: str,
        aspect_ratio: str,
        provider: str,
    ) -> CompletedNativeTool:
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            run = db.get(NativeAgentRun, self.run_id)
            if step is None or run is None:
                raise RuntimeError("Native Agent Tool Step 或 Run 不存在")
            _require_run_writable(run)
            if step.status != NativeAgentStepStatus.running:
                raise RuntimeError("Native Agent Tool Step 不是 running 状态")
            asset = FileAsset(
                purpose=FileAssetPurpose.generated_image,
                storage_backend=generated.storage_backend,
                storage_key=generated.storage_key,
                public_url=generated.public_url,
                original_filename=generated.original_filename,
                content_type=generated.content_type,
                byte_size=generated.byte_size,
                checksum_sha256=generated.checksum_sha256,
                width=generated.width,
                height=generated.height,
            )
            db.add(asset)
            db.flush()
            image = NativeAgentImage(
                run_id=self.run_id,
                asset_id=asset.id,
                prompt=prompt,
                image_model_snapshot=image_model,
                aspect_ratio_snapshot=aspect_ratio,
                provider_snapshot=provider,
                provider_request_id=generated.provider_request_id,
            )
            db.add(image)
            db.flush()
            step.status = NativeAgentStepStatus.succeeded
            step.finished_at = datetime.utcnow()
            step.error_code = None
            step.error_message = None
            step.output_ref_json = _json_dumps(
                {
                    "image_id": image.id,
                    "asset_id": asset.id,
                    "provider_request_id": generated.provider_request_id,
                    "provider": provider,
                }
            )
            run.image_call_count += 1
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_result,
                    payload_json=_json_dumps(
                        {
                            "tool": "generate_image",
                            "status": "succeeded",
                            "tool_call_id": step.tool_call_id,
                            "step_id": step.id,
                            "image_id": image.id,
                            "width": generated.width,
                            "height": generated.height,
                            "provider_request_id": generated.provider_request_id,
                            "provider": provider,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.completed",
                {
                    "step_sequence": step.sequence,
                    "tool": step.name,
                    "tool_call_id": step.tool_call_id,
                    "image_id": image.id,
                    "asset_id": asset.id,
                    "width": generated.width,
                    "height": generated.height,
                    "provider": provider,
                },
            )
            from app.services.durable_agent_runtime import (
                bind_native_agent_image,
                media_runtime_enabled,
                workflow_for_native_run,
            )

            if media_runtime_enabled(db, native_run_id=self.run_id):
                workflow = workflow_for_native_run(db, self.run_id)
                assert workflow is not None
                bind_native_agent_image(
                    db,
                    workflow=workflow,
                    native_image=image,
                    native_step=step,
                )
            db.commit()
            return self._completed_tool(db, step)

    def complete_speech_tool(
        self,
        step_id: str,
        *,
        text: str,
        generated: GeneratedSpeech,
        resource_id: str,
        model: str,
        speaker: str,
        speed: float,
        speech_rate: int,
    ) -> CompletedNativeSpeech:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
        suffix = (
            ".ogg"
            if generated.response_format == "ogg_opus"
            else f".{generated.response_format.lstrip('.')}"
        )
        stored = save_binary_file(
            FileAssetPurpose.generated_audio.value,
            generated.content,
            suffix,
        )
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            run = db.get(NativeAgentRun, self.run_id)
            if step is None or run is None:
                raise RuntimeError("Native Agent Tool Step 或 Run 不存在")
            _require_run_writable(run)
            if step.status != NativeAgentStepStatus.running:
                raise RuntimeError("Native Agent Tool Step 不是 running 状态")
            asset = FileAsset(
                purpose=FileAssetPurpose.generated_audio,
                storage_backend=stored.storage_backend,
                storage_key=stored.storage_key,
                public_url=stored.public_url,
                original_filename=f"{self.run_id}-{step.id}{suffix}",
                content_type=generated.content_type,
                byte_size=stored.byte_size,
                checksum_sha256=stored.checksum_sha256,
            )
            db.add(asset)
            db.flush()
            audio = NativeAgentAudio(
                run_id=self.run_id,
                asset_id=asset.id,
                text=text,
                provider_snapshot="volcengine",
                resource_id_snapshot=resource_id,
                model_snapshot=model,
                speaker_snapshot=speaker,
                response_format_snapshot=generated.response_format,
                sample_rate_snapshot=generated.sample_rate,
                speed_snapshot=speed,
                speech_rate_snapshot=speech_rate,
                duration_ms=generated.duration_ms,
                provider_request_id=generated.provider_request_id,
            )
            db.add(audio)
            db.flush()
            step.status = NativeAgentStepStatus.succeeded
            step.finished_at = datetime.utcnow()
            step.error_code = None
            step.error_message = None
            step.output_ref_json = _json_dumps(
                {
                    "audio_id": audio.id,
                    "asset_id": asset.id,
                    "provider_request_id": generated.provider_request_id,
                }
            )
            run.speech_call_count += 1
            result_payload = {
                "tool": "generate_speech",
                "status": "succeeded",
                "tool_call_id": step.tool_call_id,
                "step_id": step.id,
                "audio_id": audio.id,
                "asset_id": asset.id,
                "content_type": generated.content_type,
                "byte_size": stored.byte_size,
                "sample_rate": generated.sample_rate,
                "duration_ms": generated.duration_ms,
                "speed": speed,
                "speech_rate": speech_rate,
                "provider_request_id": generated.provider_request_id,
            }
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_result,
                    payload_json=_json_dumps(result_payload),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.completed",
                {
                    "step_sequence": step.sequence,
                    **result_payload,
                },
            )
            db.commit()
            return self._completed_speech(db, step)

    def complete_subtitle_tool(
        self,
        step_id: str,
        *,
        audio_id: str,
        generated: GeneratedSubtitles,
    ) -> CompletedNativeSubtitle:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
        stored = save_binary_file(
            FileAssetPurpose.generated_subtitle.value,
            generated.content,
            ".vtt",
        )
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            run = db.get(NativeAgentRun, self.run_id)
            audio = db.get(NativeAgentAudio, audio_id)
            if step is None or run is None or audio is None:
                raise RuntimeError("Native Agent Tool Step、Run 或 Audio 不存在")
            _require_run_writable(run)
            if step.status != NativeAgentStepStatus.running:
                raise RuntimeError("Native Agent Tool Step 不是 running 状态")
            if audio.run_id != self.run_id:
                raise RuntimeError("字幕音频不属于当前 Run")
            asset = FileAsset(
                purpose=FileAssetPurpose.generated_subtitle,
                storage_backend=stored.storage_backend,
                storage_key=stored.storage_key,
                public_url=stored.public_url,
                original_filename=f"{self.run_id}-{step.id}.vtt",
                content_type="text/vtt; charset=utf-8",
                byte_size=stored.byte_size,
                checksum_sha256=stored.checksum_sha256,
            )
            db.add(asset)
            db.flush()
            cues = tuple(
                {
                    "start_ms": cue.start_ms,
                    "end_ms": cue.end_ms,
                    "text": cue.text,
                }
                for cue in generated.cues
            )
            subtitle = NativeAgentSubtitle(
                run_id=self.run_id,
                audio_id=audio_id,
                asset_id=asset.id,
                provider_snapshot="faster-whisper",
                model_snapshot=generated.model,
                language=generated.language,
                text=generated.text,
                cues_json=_json_dumps(cues),
                duration_ms=generated.duration_ms,
            )
            db.add(subtitle)
            db.flush()
            step.status = NativeAgentStepStatus.succeeded
            step.finished_at = datetime.utcnow()
            step.error_code = None
            step.error_message = None
            step.output_ref_json = _json_dumps(
                {"subtitle_id": subtitle.id, "asset_id": asset.id}
            )
            run.subtitle_call_count += 1
            payload = {
                "tool": "generate_subtitles",
                "status": "succeeded",
                "tool_call_id": step.tool_call_id,
                "step_id": step.id,
                "subtitle_id": subtitle.id,
                "audio_id": audio_id,
                "asset_id": asset.id,
                "cue_count": len(cues),
                "duration_ms": generated.duration_ms,
                "language": generated.language,
                "model": generated.model,
            }
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_result,
                    payload_json=_json_dumps(payload),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.completed",
                {"step_sequence": step.sequence, **payload},
            )
            db.commit()
            return self._completed_subtitle(db, step)

    def complete_video_tool(
        self,
        step_id: str,
        *,
        scenes: list[dict[str, object]],
        bgm_asset_id: str | None,
        generated: GeneratedRemotionVideo,
    ) -> CompletedNativeVideo:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
        stored = save_binary_file(
            FileAssetPurpose.generated_video.value,
            generated.content,
            ".mp4",
        )
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            run = db.get(NativeAgentRun, self.run_id)
            if step is None or run is None:
                raise RuntimeError("Native Agent Tool Step 或 Run 不存在")
            _require_run_writable(run)
            if step.status != NativeAgentStepStatus.running:
                raise RuntimeError("Native Agent Tool Step 不是 running 状态")
            asset = FileAsset(
                purpose=FileAssetPurpose.generated_video,
                storage_backend=stored.storage_backend,
                storage_key=stored.storage_key,
                public_url=stored.public_url,
                original_filename=f"{self.run_id}-{step.id}.mp4",
                content_type=generated.content_type,
                byte_size=stored.byte_size,
                checksum_sha256=stored.checksum_sha256,
                width=generated.width,
                height=generated.height,
            )
            db.add(asset)
            db.flush()
            video = NativeAgentVideo(
                run_id=self.run_id,
                asset_id=asset.id,
                bgm_asset_id=bgm_asset_id,
                template_id_snapshot=generated.template_id,
                renderer_version_snapshot=generated.renderer_version,
                scenes_json=_json_dumps(scenes),
                duration_ms=generated.duration_ms,
                duration_in_frames=generated.duration_in_frames,
                fps=generated.fps,
                width=generated.width,
                height=generated.height,
            )
            db.add(video)
            db.flush()
            step.status = NativeAgentStepStatus.succeeded
            step.finished_at = datetime.utcnow()
            step.error_code = None
            step.error_message = None
            step.output_ref_json = _json_dumps(
                {
                    "video_id": video.id,
                    "asset_id": asset.id,
                }
            )
            run.video_call_count += 1
            result_payload = {
                "tool": "render_story_video",
                "status": "succeeded",
                "tool_call_id": step.tool_call_id,
                "step_id": step.id,
                "video_id": video.id,
                "asset_id": asset.id,
                "content_type": generated.content_type,
                "byte_size": stored.byte_size,
                "template_id": generated.template_id,
                "duration_ms": generated.duration_ms,
                "fps": generated.fps,
                "width": generated.width,
                "height": generated.height,
            }
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_result,
                    payload_json=_json_dumps(result_payload),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.completed",
                {
                    "step_sequence": step.sequence,
                    **result_payload,
                },
            )
            db.commit()
            return self._completed_video(db, step)

    def complete_external_content_tool(
        self,
        step_id: str,
        *,
        platform: str,
        content_type: str | None,
        source_url: str,
        resolved_url: str,
        source_content_id: str | None,
        title: str | None,
        description: str | None,
        author_name: str | None,
        publish_time: str | None,
        publish_timestamp: int | None,
        tags: list[str],
        metrics: dict[str, object],
        markdown: bytes,
        excerpt: str,
    ) -> CompletedNativeExternalContent:
        stored = save_binary_file(
            FileAssetPurpose.external_content.value,
            markdown,
            ".md",
        )
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            run = db.get(NativeAgentRun, self.run_id)
            if step is None or run is None:
                raise RuntimeError("Native Agent Tool Step 或 Run 不存在")
            _require_run_writable(run)
            if step.status != NativeAgentStepStatus.running:
                raise RuntimeError("Native Agent Tool Step 不是 running 状态")
            asset = FileAsset(
                purpose=FileAssetPurpose.external_content,
                storage_backend=stored.storage_backend,
                storage_key=stored.storage_key,
                public_url=stored.public_url,
                original_filename=f"{self.run_id}-{step.id}.md",
                content_type="text/markdown; charset=utf-8",
                byte_size=stored.byte_size,
                checksum_sha256=stored.checksum_sha256,
            )
            db.add(asset)
            db.flush()
            content = NativeAgentExternalContent(
                run_id=self.run_id,
                content_asset_id=asset.id,
                platform=platform,
                content_type=content_type,
                source_url=source_url,
                resolved_url=resolved_url,
                source_content_id=source_content_id,
                title=title,
                description=description,
                author_name=author_name,
                publish_time=publish_time,
                publish_timestamp=publish_timestamp,
                tags_json=_json_dumps(tags),
                metrics_json=_json_dumps(metrics),
                excerpt=excerpt,
            )
            db.add(content)
            db.flush()
            step.status = NativeAgentStepStatus.succeeded
            step.finished_at = datetime.utcnow()
            step.error_code = None
            step.error_message = None
            step.output_ref_json = _json_dumps(
                {
                    "external_content_id": content.id,
                    "asset_id": asset.id,
                }
            )
            result_payload = {
                "tool": "capture_wechat_article",
                "status": "succeeded",
                "tool_call_id": step.tool_call_id,
                "step_id": step.id,
                "external_content_id": content.id,
                "asset_id": asset.id,
                "platform": platform,
                "title": title,
                "author_name": author_name,
                "publish_time": publish_time,
                "source_url": source_url,
                "byte_size": stored.byte_size,
            }
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_result,
                    payload_json=_json_dumps(result_payload),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.completed",
                {"step_sequence": step.sequence, **result_payload},
            )
            db.commit()
            return self._completed_external_content(db, step)

    def fail_tool(self, step_id: str, exc: Exception) -> None:
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            run = db.get(NativeAgentRun, self.run_id)
            if step is None:
                raise RuntimeError("Native Agent Tool Step 不存在")
            if run is not None and run.status in {
                AgentRunStatus.cancel_requested,
                AgentRunStatus.cancelled,
            }:
                if step.status in {
                    NativeAgentStepStatus.prepared,
                    NativeAgentStepStatus.running,
                }:
                    step.status = NativeAgentStepStatus.cancelled
                    step.finished_at = datetime.utcnow()
                    step.error_code = "NativeAgentRunCancelled"
                    step.error_message = "用户已终止本轮任务"
                    db.commit()
                return
            step.status = NativeAgentStepStatus.failed
            step.finished_at = datetime.utcnow()
            step.error_code = type(exc).__name__
            step.error_message = str(exc)[:500]
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_result,
                    payload_json=_json_dumps(
                        {
                            "tool": step.name,
                            "status": "failed",
                            "tool_call_id": step.tool_call_id,
                            "step_id": step.id,
                            "error_code": step.error_code,
                            "error_message": step.error_message,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.failed",
                {
                    "step_sequence": step.sequence,
                    "tool": step.name,
                    "tool_call_id": step.tool_call_id,
                    "error_code": step.error_code,
                    "error_message": step.error_message,
                },
            )
            from app.services.durable_agent_runtime import (
                update_native_image_effect,
            )

            update_native_image_effect(
                db,
                native_step_id=step.id,
                status="failed",
                result={
                    "error_code": step.error_code,
                    "error_message": step.error_message,
                },
            )
            db.commit()

    def complete_image_inspection_tool(
        self,
        step_id: str,
        *,
        image_id: str,
        verdict: str,
        scores: dict[str, float],
        issues: list[dict[str, object]],
        provider: str,
        model: str,
        latency_ms: int,
    ) -> CompletedNativeImageInspection:
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            run = db.get(NativeAgentRun, self.run_id)
            if step is None or run is None:
                raise RuntimeError("Native Agent Tool Step 或 Run 不存在")
            _require_run_writable(run)
            if step.name != "inspect_image":
                raise RuntimeError("Native Agent Tool Step 不是 inspect_image")
            if step.status != NativeAgentStepStatus.running:
                raise RuntimeError("Native Agent Tool Step 不是 running 状态")
            image = db.get(NativeAgentImage, image_id)
            if image is None or image.run_id != self.run_id:
                raise RuntimeError("image_id 不属于当前 Run")
            output = {
                "image_id": image_id,
                "verdict": verdict,
                "scores": scores,
                "issues": issues,
                "provider": provider,
                "model": model,
                "latency_ms": latency_ms,
            }
            step.status = NativeAgentStepStatus.succeeded
            step.finished_at = datetime.utcnow()
            step.output_ref_json = _json_dumps(output)
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.tool_result,
                    payload_json=_json_dumps(
                        {
                            "tool": "inspect_image",
                            "status": "succeeded",
                            "tool_call_id": step.tool_call_id,
                            "step_id": step.id,
                            **output,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "tool.completed",
                {"step_sequence": step.sequence, "tool": "inspect_image", **output},
            )
            db.commit()
            return self._completed_image_inspection(step)

    def complete_run(self, final_output: str) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            _require_run_writable(run)
            failed_tool = db.scalar(
                select(NativeAgentStep)
                .where(
                    NativeAgentStep.run_id == self.run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.tool_call,
                    NativeAgentStep.status == NativeAgentStepStatus.failed,
                )
                .order_by(NativeAgentStep.sequence.desc())
                .limit(1)
            )
            if failed_tool is not None:
                raise RuntimeError(
                    f"{failed_tool.name} 执行失败："
                    f"{failed_tool.error_message or '未返回错误详情'}"
                )
            pending_retry = db.scalar(
                select(NativeAgentStep)
                .where(
                    NativeAgentStep.run_id == self.run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.tool_call,
                    NativeAgentStep.status == NativeAgentStepStatus.prepared,
                    NativeAgentStep.attempts > 0,
                )
                .order_by(NativeAgentStep.sequence.desc())
                .limit(1)
            )
            if pending_retry is not None:
                pending_retry.status = NativeAgentStepStatus.failed
                pending_retry.finished_at = datetime.utcnow()
                pending_retry.error_code = "NativeAgentRetryNotExecuted"
                pending_retry.error_message = "模型没有执行指定的失败 Tool 重试"
                _add_event(
                    db,
                    self.run_id,
                    "tool.retry_not_executed",
                    {
                        "step_sequence": pending_retry.sequence,
                        "tool": pending_retry.name,
                    },
                )
                db.commit()
                raise NativeAgentRetryArgumentsMismatch(
                    "模型没有执行指定的失败 Tool 重试"
                )
            step_sequence = _next_sequence(db, NativeAgentStep, self.run_id)
            step = NativeAgentStep(
                run_id=self.run_id,
                sequence=step_sequence,
                step_type=NativeAgentStepType.final,
                status=NativeAgentStepStatus.succeeded,
                name="final_output",
                idempotency_key=f"native:{self.run_id}:final:{step_sequence}",
                output_ref_json=_json_dumps({"content": final_output}),
                attempts=1,
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
            db.add(step)
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.assistant_output,
                    payload_json=_json_dumps({"content": final_output}),
                )
            )
            run.status = AgentRunStatus.succeeded
            run.final_output = final_output
            run.finished_at = datetime.utcnow()
            _add_event(
                db,
                self.run_id,
                "checkpoint.saved",
                {"through_step_sequence": step.sequence},
            )
            _add_event(
                db,
                self.run_id,
                "run.completed",
                {"status": "succeeded"},
            )
            db.commit()

    def pause_for_article_approval(self, final_output: str) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            if run.status in {
                AgentRunStatus.cancel_requested,
                AgentRunStatus.cancelled,
            }:
                raise NativeAgentRunCancelled("Native Agent Run 已请求取消")
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.assistant_output,
                    payload_json=_json_dumps({"content": final_output}),
                )
            )
            run.status = AgentRunStatus.waiting_for_input
            run.final_output = final_output
            run.finished_at = None
            _add_event(
                db,
                self.run_id,
                "checkpoint.saved",
                {
                    "phase": "waiting_for_article_approval",
                    "workflow_revision": run.workflow_revision,
                },
            )
            _add_event(
                db,
                self.run_id,
                "run.waiting_for_input",
                {"status": "waiting_for_input"},
            )
            db.commit()

    def pause_for_media_quality(self, final_output: str) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            if run.status in {
                AgentRunStatus.cancel_requested,
                AgentRunStatus.cancelled,
            }:
                raise NativeAgentRunCancelled("Native Agent Run 已请求取消")
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.assistant_output,
                    payload_json=_json_dumps({"content": final_output}),
                )
            )
            run.status = AgentRunStatus.waiting_for_input
            run.workflow_phase = "image_quality_pending"
            run.final_output = final_output
            run.finished_at = None
            _add_event(
                db,
                self.run_id,
                "checkpoint.saved",
                {"phase": "waiting_for_image_quality"},
            )
            _add_event(
                db,
                self.run_id,
                "run.waiting_for_input",
                {"status": "waiting_for_input", "kind": "image_quality"},
            )
            db.commit()

    def fail_run(self, exc: Exception) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                return
            if run.status in {
                AgentRunStatus.cancel_requested,
                AgentRunStatus.cancelled,
            }:
                return
            error_code = type(exc).__name__
            error_message = str(exc)[:500]
            run.status = AgentRunStatus.failed
            run.error_code = error_code
            run.error_message = error_message
            run.finished_at = datetime.utcnow()
            db.add(
                NativeAgentItem(
                    run_id=self.run_id,
                    sequence=_next_sequence(db, NativeAgentItem, self.run_id),
                    item_type=NativeAgentItemType.error,
                    payload_json=_json_dumps(
                        {
                            "error_code": error_code,
                            "error_message": error_message,
                        }
                    ),
                )
            )
            _add_event(
                db,
                self.run_id,
                "run.failed",
                {
                    "status": "failed",
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )
            db.commit()

    def cancel_run(self) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            if run.status == AgentRunStatus.cancelled:
                return
            if run.status in {
                AgentRunStatus.succeeded,
                AgentRunStatus.failed,
            }:
                raise RuntimeError("已结束的 Native Agent Run 不能取消")
            now = datetime.utcnow()
            active_steps = db.scalars(
                select(NativeAgentStep)
                .where(
                    NativeAgentStep.run_id == self.run_id,
                    NativeAgentStep.status.in_(
                        [
                            NativeAgentStepStatus.prepared,
                            NativeAgentStepStatus.running,
                        ]
                    ),
                )
                .order_by(NativeAgentStep.sequence.asc())
            ).all()
            for step in active_steps:
                step.status = NativeAgentStepStatus.cancelled
                step.finished_at = now
                step.error_code = "NativeAgentRunCancelled"
                step.error_message = "用户已终止本轮任务"
                _add_event(
                    db,
                    self.run_id,
                    "tool.cancelled",
                    {
                        "step_sequence": step.sequence,
                        "tool": step.name,
                        "tool_call_id": step.tool_call_id,
                    },
                )
            run.status = AgentRunStatus.cancelled
            run.finished_at = now
            run.error_code = None
            run.error_message = None
            _add_event(
                db,
                self.run_id,
                "run.cancelled",
                {"status": AgentRunStatus.cancelled.value},
            )
            db.commit()

    def mark_step_unknown(self, step_id: str, message: str) -> None:
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            if step is None:
                return
            step.status = NativeAgentStepStatus.unknown
            step.finished_at = datetime.utcnow()
            step.error_code = "NativeAgentToolOutcomeUnknown"
            step.error_message = message
            _add_event(
                db,
                self.run_id,
                "tool.unknown",
                {
                    "step_sequence": step.sequence,
                    "tool": step.name,
                    "tool_call_id": step.tool_call_id,
                    "error_code": step.error_code,
                    "error_message": message,
                },
            )
            from app.services.durable_agent_runtime import (
                update_native_image_effect,
            )

            update_native_image_effect(
                db,
                native_step_id=step.id,
                status="unknown",
                result={"error_message": message},
            )
            db.commit()

    @staticmethod
    def _completed_tool(
        db: Session,
        step: NativeAgentStep,
    ) -> CompletedNativeTool:
        output = json.loads(step.output_ref_json or "{}")
        image_id = str(output.get("image_id") or "")
        if not image_id:
            raise RuntimeError("成功 Tool Step 缺少 image_id")
        image = db.scalar(
            select(NativeAgentImage)
            .where(NativeAgentImage.id == image_id)
            .options(selectinload(NativeAgentImage.asset))
        )
        if image is None:
            raise RuntimeError("成功 Tool Step 引用的图片不存在")
        return CompletedNativeTool(
            step_id=step.id,
            image_id=image.id,
            asset_id=image.asset_id,
            storage_backend=image.asset.storage_backend,
            storage_key=image.asset.storage_key,
            public_url=image.asset.public_url,
            content_type=image.asset.content_type,
            width=image.asset.width,
            height=image.asset.height,
            provider_request_id=image.provider_request_id,
        )

    @staticmethod
    def _completed_image_inspection(
        step: NativeAgentStep,
    ) -> CompletedNativeImageInspection:
        output = json.loads(step.output_ref_json or "{}")
        if not output.get("image_id") or not output.get("verdict"):
            raise RuntimeError("成功 inspect_image Step 缺少检查结果")
        return CompletedNativeImageInspection(
            step_id=step.id,
            image_id=str(output["image_id"]),
            verdict=str(output["verdict"]),
            scores={str(key): float(value) for key, value in output.get("scores", {}).items()},
            issues=list(output.get("issues", [])),
            provider=str(output.get("provider") or ""),
            model=str(output.get("model") or ""),
            latency_ms=int(output.get("latency_ms") or 0),
        )

    @staticmethod
    def _completed_speech(
        db: Session,
        step: NativeAgentStep,
    ) -> CompletedNativeSpeech:
        output = json.loads(step.output_ref_json or "{}")
        audio_id = str(output.get("audio_id") or "")
        if not audio_id:
            raise RuntimeError("成功 Tool Step 缺少 audio_id")
        audio = db.scalar(
            select(NativeAgentAudio)
            .where(NativeAgentAudio.id == audio_id)
            .options(selectinload(NativeAgentAudio.asset))
        )
        if audio is None:
            raise RuntimeError("成功 Tool Step 引用的音频不存在")
        return CompletedNativeSpeech(
            step_id=step.id,
            audio_id=audio.id,
            asset_id=audio.asset_id,
            text=audio.text,
            content_type=audio.asset.content_type,
            byte_size=audio.asset.byte_size,
            response_format=audio.response_format_snapshot,
            sample_rate=audio.sample_rate_snapshot,
            duration_ms=audio.duration_ms,
            speed=audio.speed_snapshot,
            speech_rate=audio.speech_rate_snapshot,
            provider_request_id=audio.provider_request_id,
        )

    @staticmethod
    def _completed_subtitle(
        db: Session,
        step: NativeAgentStep,
    ) -> CompletedNativeSubtitle:
        output = json.loads(step.output_ref_json or "{}")
        subtitle_id = str(output.get("subtitle_id") or "")
        subtitle = db.scalar(
            select(NativeAgentSubtitle)
            .where(NativeAgentSubtitle.id == subtitle_id)
            .options(selectinload(NativeAgentSubtitle.asset))
        )
        if subtitle is None:
            raise RuntimeError("成功 Tool Step 引用的字幕不存在")
        return CompletedNativeSubtitle(
            step_id=step.id,
            subtitle_id=subtitle.id,
            audio_id=subtitle.audio_id,
            asset_id=subtitle.asset_id,
            content_type=subtitle.asset.content_type,
            byte_size=subtitle.asset.byte_size,
            text=subtitle.text,
            language=subtitle.language,
            model=subtitle.model_snapshot,
            duration_ms=subtitle.duration_ms,
            cues=tuple(json.loads(subtitle.cues_json)),
        )

    @staticmethod
    def _completed_video(
        db: Session,
        step: NativeAgentStep,
    ) -> CompletedNativeVideo:
        output = json.loads(step.output_ref_json or "{}")
        video_id = str(output.get("video_id") or "")
        if not video_id:
            raise RuntimeError("成功 Tool Step 缺少 video_id")
        video = db.scalar(
            select(NativeAgentVideo)
            .where(NativeAgentVideo.id == video_id)
            .options(selectinload(NativeAgentVideo.asset))
        )
        if video is None:
            raise RuntimeError("成功 Tool Step 引用的视频不存在")
        return CompletedNativeVideo(
            step_id=step.id,
            video_id=video.id,
            asset_id=video.asset_id,
            content_type=video.asset.content_type,
            byte_size=video.asset.byte_size,
            template_id=video.template_id_snapshot,
            renderer_version=video.renderer_version_snapshot,
            duration_ms=video.duration_ms,
            duration_in_frames=video.duration_in_frames,
            fps=video.fps,
            width=video.width,
            height=video.height,
            bgm_asset_id=video.bgm_asset_id,
        )

    @staticmethod
    def _completed_external_content(
        db: Session,
        step: NativeAgentStep,
    ) -> CompletedNativeExternalContent:
        output = json.loads(step.output_ref_json or "{}")
        content_id = str(output.get("external_content_id") or "")
        if not content_id:
            raise RuntimeError("成功 Tool Step 缺少 external_content_id")
        content = db.scalar(
            select(NativeAgentExternalContent)
            .where(NativeAgentExternalContent.id == content_id)
            .options(selectinload(NativeAgentExternalContent.content_asset))
        )
        if content is None:
            raise RuntimeError("成功 Tool Step 引用的外部内容不存在")
        return CompletedNativeExternalContent(
            step_id=step.id,
            external_content_id=content.id,
            asset_id=content.content_asset_id,
            platform=content.platform,
            title=content.title,
            author_name=content.author_name,
            publish_time=content.publish_time,
            source_url=content.source_url,
            excerpt=content.excerpt,
            byte_size=content.content_asset.byte_size,
        )
