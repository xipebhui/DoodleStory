from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from agents.items import TResponseInputItem
from agents.memory.session import SessionABC
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker, selectinload

from app.core.database import SessionLocal
from app.models.entities import (
    FileAsset,
    NativeAgentContextItem,
    NativeAgentEvent,
    NativeAgentImage,
    NativeAgentItem,
    NativeAgentRun,
    NativeAgentStep,
)
from app.models.enums import (
    AgentRunStatus,
    FileAssetPurpose,
    NativeAgentItemType,
    NativeAgentStepStatus,
    NativeAgentStepType,
)
from app.services.image_generation import GeneratedImageFile


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
    | type[NativeAgentEvent]
    | type[NativeAgentContextItem],
    run_id: str,
) -> int:
    latest = db.scalar(select(func.max(model.sequence)).where(model.run_id == run_id))
    return int(latest or 0) + 1


def _add_event(
    db: Session,
    run_id: str,
    event_type: str,
    payload: dict[str, object],
) -> NativeAgentEvent:
    event = NativeAgentEvent(
        run_id=run_id,
        sequence=_next_sequence(db, NativeAgentEvent, run_id),
        event_type=event_type,
        payload_json=_json_dumps(payload),
    )
    db.add(event)
    db.flush()
    return event


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

    def append_event(
        self,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        with self._session_factory() as db:
            _add_event(db, self.run_id, event_type, payload)
            db.commit()

    def start_run(self, *, resumed: bool) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            run.status = AgentRunStatus.running
            if run.started_at is None:
                run.started_at = datetime.utcnow()
            run.error_code = None
            run.error_message = None
            run.finished_at = None
            event_type = "run.resumed" if resumed else "run.started"
            _add_event(
                db,
                self.run_id,
                event_type,
                {"status": "running"},
            )
            db.commit()

    def start_model_step(self, response_id: str) -> NativeAgentStep:
        with self._session_factory() as db:
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
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            run.model_call_count += 1
            _add_event(
                db,
                self.run_id,
                "response.started",
                {
                    "step_sequence": step.sequence,
                    "response_id": response_id,
                    "model_call_count": run.model_call_count,
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
    ) -> CompletedNativeTool | NativeAgentStep:
        idempotency_key = (
            f"native:{self.run_id}:generate_image:{tool_call_id}"
        )
        with self._session_factory() as db:
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
                input_summary_json=_json_dumps({"prompt": prompt}),
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
                            "tool": "generate_image",
                            "prompt": prompt,
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
                    "arguments": {"prompt": prompt},
                },
            )
            db.commit()
            db.refresh(step)
            return step

    def start_tool(self, step_id: str) -> None:
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            if step is None:
                raise RuntimeError("Native Agent Tool Step 不存在")
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
            db.commit()

    def complete_tool(
        self,
        step_id: str,
        *,
        prompt: str,
        generated: GeneratedImageFile,
        image_model: str,
        aspect_ratio: str,
    ) -> CompletedNativeTool:
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            run = db.get(NativeAgentRun, self.run_id)
            if step is None or run is None:
                raise RuntimeError("Native Agent Tool Step 或 Run 不存在")
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
                provider_request_id=generated.provider_request_id,
            )
            db.add(image)
            db.flush()
            step.status = NativeAgentStepStatus.succeeded
            step.finished_at = datetime.utcnow()
            step.output_ref_json = _json_dumps(
                {
                    "image_id": image.id,
                    "asset_id": asset.id,
                    "provider_request_id": generated.provider_request_id,
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
                },
            )
            db.commit()
            return self._completed_tool(db, step)

    def fail_tool(self, step_id: str, exc: Exception) -> None:
        with self._session_factory() as db:
            step = db.get(NativeAgentStep, step_id)
            if step is None:
                raise RuntimeError("Native Agent Tool Step 不存在")
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
                            "tool": "generate_image",
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
            db.commit()

    def complete_run(self, final_output: str) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
                raise RuntimeError("Native Agent Run 不存在")
            step = NativeAgentStep(
                run_id=self.run_id,
                sequence=_next_sequence(db, NativeAgentStep, self.run_id),
                step_type=NativeAgentStepType.final,
                status=NativeAgentStepStatus.succeeded,
                name="final_output",
                idempotency_key=f"native:{self.run_id}:final",
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

    def fail_run(self, exc: Exception) -> None:
        with self._session_factory() as db:
            run = db.get(NativeAgentRun, self.run_id)
            if run is None:
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
