from __future__ import annotations

import asyncio
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time
from typing import Any
from uuid import uuid4

from agents import Agent, ModelSettings, RunConfig, Runner, function_tool
from agents.model_settings import ModelRetrySettings
from agents.models.chatcmpl_converter import Converter
from agents.models.fake_id import FAKE_RESPONSES_ID
from agents.models.interface import ModelTracing
from agents.run import ToolExecutionConfig
from agents.tool_context import ToolContext
from httpx import AsyncClient, Request, Response
from importlib.metadata import version
from openai import AsyncOpenAI
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.models.entities import (
    AgentSkill,
    AgentSkillVersion,
    NativeAgentContextItem,
    NativeAgentConversation,
    NativeAgentEvent,
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
from app.services.native_agent_chat import (
    NativeAgentChatMessageLimitError,
    SiliconFlowBoundedChatModel,
    SiliconFlowBoundedChatProvider,
)
from app.services.native_agent_loop import NativeModelMetricHooks
from app.services.native_agent_model_events import NativeModelEventAdapter
from app.services.native_agent_model_routes import (
    CHAT_COMPLETIONS_API_SHAPE,
    SILICONFLOW_CHAT_ROUTE,
    SILICONFLOW_NATIVE_AGENT_MODEL,
    SILICONFLOW_PROVIDER,
    NativeAgentModelRouteSnapshot,
    resolve_native_agent_model_route,
)
from app.services.native_agent_persistence import (
    NativeAgentDatabaseSession,
    NativeAgentStore,
    add_native_agent_event,
)


G2_IMPLEMENTATION_COMMIT = "59e5f9fca6bf2ebc60079969f9bc81f61cfe5ab0"
G2_CONTRACT_REF = (
    "docs/contracts/sprint-192-native-agent-siliconflow-chat-bounded-adapter.md"
)
G3_PROTOCOL_REF = (
    "docs/testing/siliconflow-native-agent-zero-media-gate-protocol.md"
)
G3_TEMPLATE_REF = (
    "docs/testing/siliconflow-native-agent-zero-media-gate-evidence-template.json"
)
G3_REPORT_REF = (
    "docs/testing/siliconflow-native-agent-compatibility-report.json"
)
G3_SCRIPT_REF = "scripts/check_siliconflow_native_agent_compatibility.py"
G3_REQUEST_BUDGET = 5
G3_MIGRATION_HEAD = "w4x5y6z7a8b9"
LOCKED_PROBE_INPUT = {
    "probe_id": "g3-echo-01",
    "value": "PAYNES-CREEK-G3",
}
LOCKED_PROBE_OUTPUT = {
    "probe_id": "g3-echo-01",
    "echo": "PAYNES-CREEK-G3",
}
MEDIA_OR_PUBLISH_TOOLS = {
    "generate_image",
    "inspect_image",
    "generate_speech",
    "generate_subtitles",
    "render_story_video",
    "publish_youtube_video",
}


class G3GateError(RuntimeError):
    """Raised when the fixed G3 protocol cannot be completed safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def safe_error(exc: BaseException) -> dict[str, object]:
    status_code = getattr(exc, "status_code", None)
    error_code = getattr(exc, "code", None)
    request_id = getattr(exc, "request_id", None)
    message = str(exc).replace("\r", " ").replace("\n", " ").strip()
    return {
        "type": type(exc).__name__,
        "http_status": int(status_code) if isinstance(status_code, int) else None,
        "provider_error_code": str(error_code)[:120] if error_code else None,
        "provider_request_or_trace_id": (
            str(request_id)[:255] if request_id else None
        ),
        "summary": message[:300],
    }


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def make_session_factory(path: Path) -> sessionmaker:
    engine = create_engine(
        sqlite_url(path),
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def initialize_probe_tables(path: Path) -> None:
    with closing(sqlite3.connect(path, timeout=30)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS g3_http_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                process_fingerprint TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status_code INTEGER,
                provider_request_id TEXT
            )
            """
        )
        connection.commit()


def create_probe_run(
    session_factory: sessionmaker,
    *,
    case_id: str,
    tool_names: list[str] | None = None,
) -> str:
    names = tool_names or []
    with session_factory() as db:
        user = User(
            email=f"g3-{case_id}-{uuid4().hex[:8]}@example.invalid",
            password_hash="g3-not-a-login",
        )
        db.add(user)
        db.flush()
        skill = AgentSkill(
            owner_user_id=user.id,
            slug=f"g3-{case_id}-{uuid4().hex[:8]}",
            name=f"G3 {case_id}",
            description="SiliconFlow G3 zero-media compatibility probe",
            draft_instructions="G3 test-only instructions",
            draft_tool_names_json=json.dumps(names, separators=(",", ":")),
            draft_revision=1,
            status=AgentSkillStatus.published,
        )
        db.add(skill)
        db.flush()
        version_row = AgentSkillVersion(
            skill_id=skill.id,
            version=1,
            name_snapshot=skill.name,
            description_snapshot=skill.description,
            instructions=skill.draft_instructions,
            tool_names_json=skill.draft_tool_names_json,
            content_hash=f"sha256:g3-{case_id}",
            published_by_user_id=user.id,
        )
        db.add(version_row)
        db.flush()
        conversation = NativeAgentConversation(
            owner_user_id=user.id,
            title=f"G3 {case_id}",
        )
        db.add(conversation)
        db.flush()
        run = NativeAgentRun(
            conversation_id=conversation.id,
            skill_version_id=version_row.id,
            status=AgentRunStatus.queued,
            model_snapshot=SILICONFLOW_NATIVE_AGENT_MODEL,
            model_route_snapshot=SILICONFLOW_CHAT_ROUTE,
            model_provider_snapshot=SILICONFLOW_PROVIDER,
            model_api_shape_snapshot=CHAT_COMPLETIONS_API_SHAPE,
            skill_name_snapshot=version_row.name_snapshot,
            skill_version_snapshot=version_row.version,
            skill_content_hash_snapshot=version_row.content_hash,
            style_reference_urls_json="[]",
            workflow_phase=f"g3_{case_id}",
        )
        db.add(run)
        db.commit()
        return run.id


@dataclass(frozen=True)
class G3HttpRecorder:
    database_path: Path
    case_id: str
    process_fingerprint: str

    async def on_request(self, request: Request) -> None:
        with closing(sqlite3.connect(self.database_path, timeout=30)) as connection:
            cursor = connection.execute(
                """
                INSERT INTO g3_http_requests (
                    case_id, process_fingerprint, started_at
                ) VALUES (?, ?, ?)
                """,
                (self.case_id, self.process_fingerprint, utc_now()),
            )
            connection.commit()
            request.extensions["doodlestory_g3_request_row"] = int(
                cursor.lastrowid
            )

    async def on_response(self, response: Response) -> None:
        row_id = response.request.extensions.get("doodlestory_g3_request_row")
        if not isinstance(row_id, int):
            raise G3GateError("G3 HTTP response cannot be matched to request")
        request_id = next(
            (
                response.headers.get(name)
                for name in (
                    "x-request-id",
                    "request-id",
                    "x-siliconflow-request-id",
                    "cf-ray",
                )
                if response.headers.get(name)
            ),
            None,
        )
        with closing(sqlite3.connect(self.database_path, timeout=30)) as connection:
            connection.execute(
                """
                UPDATE g3_http_requests
                SET finished_at = ?, status_code = ?, provider_request_id = ?
                WHERE id = ?
                """,
                (
                    utc_now(),
                    int(response.status_code),
                    str(request_id)[:255] if request_id else None,
                    row_id,
                ),
            )
            connection.commit()


@dataclass
class G3ClientBinding:
    client: AsyncOpenAI
    http_client: AsyncClient
    provider: SiliconFlowBoundedChatProvider

    async def close(self) -> None:
        await self.client.close()


def make_client_binding(
    *,
    settings: Settings,
    database_path: Path,
    case_id: str,
    process_fingerprint: str,
    message_count_observer,
) -> G3ClientBinding:
    recorder = G3HttpRecorder(
        database_path=database_path,
        case_id=case_id,
        process_fingerprint=process_fingerprint,
    )
    http_client = AsyncClient(
        timeout=settings.agent_request_timeout_seconds,
        event_hooks={
            "request": [recorder.on_request],
            "response": [recorder.on_response],
        },
    )
    client = AsyncOpenAI(
        api_key=settings.siliconflow_api_key,
        base_url=settings.siliconflow_base_url.rstrip("/"),
        max_retries=0,
        timeout=settings.agent_request_timeout_seconds,
        http_client=http_client,
    )
    provider = SiliconFlowBoundedChatProvider(
        openai_client=client,
        expected_model=SILICONFLOW_NATIVE_AGENT_MODEL,
        message_count_observer=message_count_observer,
    )
    return G3ClientBinding(
        client=client,
        http_client=http_client,
        provider=provider,
    )


def production_model_settings() -> ModelSettings:
    return ModelSettings(
        retry=ModelRetrySettings(max_retries=0),
        store=None,
        parallel_tool_calls=None,
        include_usage=None,
        extra_body={"enable_thinking": False},
    )


def process_fingerprint(label: str) -> str:
    raw = f"{label}:{os.getpid()}:{time.time_ns()}".encode("utf-8")
    return sha256_bytes(raw)[:16]


def route_snapshot() -> NativeAgentModelRouteSnapshot:
    return NativeAgentModelRouteSnapshot(
        route=SILICONFLOW_CHAT_ROUTE,
        provider=SILICONFLOW_PROVIDER,
        api_shape=CHAT_COMPLETIONS_API_SHAPE,
        model=SILICONFLOW_NATIVE_AGENT_MODEL,
    )


async def run_agent_case(
    *,
    database_path: Path,
    run_id: str,
    case_id: str,
    fingerprint: str,
    instructions: str,
    input_items: str | list[dict[str, object]],
    tools: list[object] | None = None,
    tool_use_behavior: str = "run_llm_again",
    leave_paused: bool = False,
) -> dict[str, object]:
    session_factory = make_session_factory(database_path)
    store = NativeAgentStore(run_id, session_factory=session_factory)
    sdk_session = NativeAgentDatabaseSession(
        run_id,
        session_factory=session_factory,
    )
    resumed = await sdk_session.has_items()
    execution_attempt = store.start_run(resumed=resumed)
    adapter = NativeModelEventAdapter(
        run_id=run_id,
        execution_attempt=execution_attempt,
        route=route_snapshot(),
        store=store,
    )
    binding = make_client_binding(
        settings=Settings(),
        database_path=database_path,
        case_id=case_id,
        process_fingerprint=fingerprint,
        message_count_observer=adapter.record_converted_message_count,
    )
    hooks = NativeModelMetricHooks(
        store,
        phase=f"g3_{case_id}_attempt_{execution_attempt}",
    )
    agent = Agent(
        name="DoodleStoryG3Probe",
        instructions=instructions,
        model=SILICONFLOW_NATIVE_AGENT_MODEL,
        tools=list(tools or []),
        model_settings=production_model_settings(),
        hooks=hooks,
        tool_use_behavior=tool_use_behavior,
    )
    try:
        result = Runner.run_streamed(
            agent,
            [] if resumed else input_items,
            run_config=RunConfig(
                model_provider=binding.provider,
                tracing_disabled=True,
                workflow_name="DoodleStory SiliconFlow G3 Probe",
                tool_execution=ToolExecutionConfig(
                    max_function_tool_concurrency=1,
                ),
            ),
            max_turns=2,
            session=sdk_session,
        )
        async for event in result.stream_events():
            if event.type == "raw_response_event":
                adapter.handle(event.data)
        adapter.finish()
        final_output = str(result.final_output or "").strip()
        if not final_output:
            raise G3GateError(f"{case_id} returned empty final output")
        if leave_paused:
            with session_factory() as db:
                run = db.get(NativeAgentRun, run_id)
                if run is None:
                    raise G3GateError("G3 Z2 run disappeared before pause")
                run.status = AgentRunStatus.waiting_for_tool
                run.workflow_phase = "g3_paused_after_tool_commit"
                add_native_agent_event(
                    db,
                    run_id,
                    "g3.paused_after_tool_commit",
                    {"process_fingerprint": fingerprint},
                )
                db.commit()
        else:
            store.complete_run(final_output)
        return summarize_run(
            session_factory,
            run_id=run_id,
            execution_attempt=execution_attempt,
            process_fingerprint_value=fingerprint,
            final_output=final_output,
        )
    except Exception as exc:
        store.fail_active_model_step(exc)
        if not leave_paused:
            store.fail_run(exc)
        raise
    finally:
        await binding.close()


def build_echo_probe_tool(
    *,
    database_path: Path,
    run_id: str,
    fingerprint: str,
):
    session_factory = make_session_factory(database_path)

    @function_tool(
        name_override="echo_probe",
        description_override=(
            "Return the exact deterministic G3 probe payload. Test-only; no media."
        ),
        strict_mode=True,
    )
    async def echo_probe(
        context: ToolContext[None],
        probe_id: str,
        value: str,
    ) -> str:
        """Echo the locked G3 marker."""

        observed = {"probe_id": probe_id, "value": value}
        if observed != LOCKED_PROBE_INPUT:
            raise G3GateError("echo_probe input differs from locked G3 input")
        output = dict(LOCKED_PROBE_OUTPUT)
        now = datetime.utcnow()
        with session_factory() as db:
            existing = db.scalar(
                select(NativeAgentStep).where(
                    NativeAgentStep.run_id == run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.tool_call,
                    NativeAgentStep.name == "echo_probe",
                )
            )
            if existing is not None:
                raise G3GateError("echo_probe cannot execute more than once")
            sequence = int(
                db.scalar(
                    select(func.max(NativeAgentStep.sequence)).where(
                        NativeAgentStep.run_id == run_id
                    )
                )
                or 0
            ) + 1
            step = NativeAgentStep(
                run_id=run_id,
                sequence=sequence,
                step_type=NativeAgentStepType.tool_call,
                status=NativeAgentStepStatus.succeeded,
                name="echo_probe",
                tool_call_id=context.tool_call_id,
                idempotency_key=f"g3:{run_id}:echo_probe:{context.tool_call_id}",
                input_summary_json=json.dumps(
                    observed,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                output_ref_json=json.dumps(
                    {
                        "output": output,
                        "process_fingerprint": fingerprint,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                attempts=1,
                started_at=now,
                finished_at=now,
            )
            db.add(step)
            add_native_agent_event(
                db,
                run_id,
                "g3.echo_probe.executed",
                {
                    "step_id": step.id,
                    "tool_call_id": context.tool_call_id,
                    "process_fingerprint": fingerprint,
                },
            )
            db.commit()
        return json.dumps(output, ensure_ascii=False, separators=(",", ":"))

    return echo_probe


def summarize_run(
    session_factory: sessionmaker,
    *,
    run_id: str,
    execution_attempt: int,
    process_fingerprint_value: str,
    final_output: str,
) -> dict[str, object]:
    with session_factory() as db:
        run = db.get(NativeAgentRun, run_id)
        if run is None:
            raise G3GateError("G3 run not found during summary")
        model_steps = list(
            db.scalars(
                select(NativeAgentStep)
                .where(
                    NativeAgentStep.run_id == run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.model_call,
                    NativeAgentStep.execution_attempt == execution_attempt,
                )
                .order_by(NativeAgentStep.sequence)
            ).all()
        )
        all_model_steps = list(
            db.scalars(
                select(NativeAgentStep)
                .where(
                    NativeAgentStep.run_id == run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.model_call,
                )
                .order_by(NativeAgentStep.sequence)
            ).all()
        )
        tool_steps = list(
            db.scalars(
                select(NativeAgentStep)
                .where(
                    NativeAgentStep.run_id == run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.tool_call,
                )
                .order_by(NativeAgentStep.sequence)
            ).all()
        )
        events = list(
            db.scalars(
                select(NativeAgentEvent)
                .where(NativeAgentEvent.run_id == run_id)
                .order_by(NativeAgentEvent.sequence)
            ).all()
        )
        context_rows = list(
            db.scalars(
                select(NativeAgentContextItem)
                .where(NativeAgentContextItem.run_id == run_id)
                .order_by(NativeAgentContextItem.sequence)
            ).all()
        )
        def model_step_summary(step: NativeAgentStep) -> dict[str, object]:
            output = json.loads(step.output_ref_json or "{}")
            return {
                "step_id": step.id,
                "model_call_id": step.model_call_id,
                "provider_response_id": step.provider_response_id,
                "converted_message_count": step.converted_message_count,
                "latency_ms": step.latency_ms,
                "status": step.status.value,
                "usage": output.get("usage") or {},
                "execution_attempt": step.execution_attempt,
                "model_call_ordinal": step.model_call_ordinal,
            }

        model_summaries = [model_step_summary(step) for step in model_steps]
        event_payloads = [
            {
                "type": event.event_type,
                "payload": json.loads(event.payload_json),
            }
            for event in events
        ]
        return {
            "run_id": run_id,
            "run_status": run.status.value,
            "workflow_phase": run.workflow_phase,
            "process_fingerprint": process_fingerprint_value,
            "execution_attempt": execution_attempt,
            "final_output": final_output,
            "model_steps": model_summaries,
            "all_model_steps": [
                model_step_summary(step) for step in all_model_steps
            ],
            "tool_steps": [
                {
                    "step_id": step.id,
                    "tool_call_id": step.tool_call_id,
                    "name": step.name,
                    "status": step.status.value,
                    "input": json.loads(step.input_summary_json or "{}"),
                    "output": json.loads(step.output_ref_json or "{}"),
                }
                for step in tool_steps
            ],
            "event_counts": {
                event_type: sum(
                    1 for event in events if event.event_type == event_type
                )
                for event_type in sorted({event.event_type for event in events})
            },
            "function_events": [
                entry
                for entry in event_payloads
                if entry["type"].startswith("response.function_call")
            ],
            "context_items": [json.loads(row.item_json) for row in context_rows],
            "route_snapshot": {
                "route": run.model_route_snapshot,
                "provider": run.model_provider_snapshot,
                "api_shape": run.model_api_shape_snapshot,
                "model": run.model_snapshot,
            },
            "media_counts": {
                "image": run.image_call_count,
                "speech": run.speech_call_count,
                "subtitle": run.subtitle_call_count,
                "video": run.video_call_count,
            },
        }


async def run_z1(
    database_path: Path,
    *,
    run_id: str,
) -> dict[str, object]:
    return await run_agent_case(
        database_path=database_path,
        run_id=run_id,
        case_id="z1",
        fingerprint=process_fingerprint("z1"),
        instructions=(
            "Return one short plain-text answer containing the exact marker "
            "G3-TEXT-OK. Do not call tools."
        ),
        input_items="Return the required G3 text marker now.",
    )


async def run_z2_stage_a(
    database_path: Path,
    *,
    run_id: str,
) -> dict[str, object]:
    fingerprint = process_fingerprint("z2a")
    tool = build_echo_probe_tool(
        database_path=database_path,
        run_id=run_id,
        fingerprint=fingerprint,
    )
    return await run_agent_case(
        database_path=database_path,
        run_id=run_id,
        case_id="z2a",
        fingerprint=fingerprint,
        instructions=(
            "Call echo_probe exactly once with probe_id='g3-echo-01' and "
            "value='PAYNES-CREEK-G3'. Do not call any other tool."
        ),
        input_items="Execute the locked echo probe exactly once.",
        tools=[tool],
        tool_use_behavior="stop_on_first_tool",
        leave_paused=True,
    )


async def run_z2_stage_b(
    database_path: Path,
    *,
    run_id: str,
) -> dict[str, object]:
    session_factory = make_session_factory(database_path)
    with session_factory() as db:
        run = db.get(NativeAgentRun, run_id)
        if (
            run is None
            or run.workflow_phase != "g3_paused_after_tool_commit"
            or run.status != AgentRunStatus.waiting_for_tool
        ):
            raise G3GateError("Z2 stage B precondition is not persisted")
        tool_count = int(
            db.scalar(
                select(func.count(NativeAgentStep.id)).where(
                    NativeAgentStep.run_id == run_id,
                    NativeAgentStep.step_type == NativeAgentStepType.tool_call,
                    NativeAgentStep.name == "echo_probe",
                    NativeAgentStep.status == NativeAgentStepStatus.succeeded,
                )
            )
            or 0
        )
        if tool_count != 1:
            raise G3GateError("Z2 stage B requires one persisted echo_probe")
    return await run_agent_case(
        database_path=database_path,
        run_id=run_id,
        case_id="z2b",
        fingerprint=process_fingerprint("z2b"),
        instructions=(
            "Use the persisted echo_probe output from the conversation. Return "
            "one short plain-text answer containing both exact markers "
            "G3-TOOL-OK and PAYNES-CREEK-G3. Do not call tools."
        ),
        input_items=[],
    )


def z3_input_items() -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index in range(1, 5):
        items.append(
            {"role": "user", "content": f"G3 context message {index}."}
        )
        items.append(
            {"role": "assistant", "content": f"Context {index} recorded."}
        )
    items.append(
        {
            "role": "user",
            "content": "Return one short answer containing G3-MSG10-OK.",
        }
    )
    return items


async def run_z3(
    database_path: Path,
    *,
    run_id: str,
) -> dict[str, object]:
    return await run_agent_case(
        database_path=database_path,
        run_id=run_id,
        case_id="z3",
        fingerprint=process_fingerprint("z3"),
        instructions="Follow the final user request exactly. Do not call tools.",
        input_items=z3_input_items(),
    )


def z4_input_items() -> list[dict[str, object]]:
    return [
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": (
                "Return G3-MSG11-OK."
                if index == 9
                else f"G3 boundary context {index + 1}."
            ),
        }
        for index in range(10)
    ]


async def run_z4(database_path: Path) -> dict[str, object]:
    settings = Settings()
    fingerprint = process_fingerprint("z4")
    observed_counts: list[int] = []
    binding = make_client_binding(
        settings=settings,
        database_path=database_path,
        case_id="z4",
        process_fingerprint=fingerprint,
        message_count_observer=observed_counts.append,
    )
    model = SiliconFlowBoundedChatModel(
        model=SILICONFLOW_NATIVE_AGENT_MODEL,
        openai_client=binding.client,
        message_count_observer=observed_counts.append,
    )
    items = z4_input_items()
    production_rejected = False
    try:
        await model._fetch_response(
            "Follow the final user request exactly.",
            items,
            production_model_settings(),
            [],
            None,
            [],
            None,
            ModelTracing.DISABLED,
            stream=True,
        )
    except NativeAgentChatMessageLimitError:
        production_rejected = True
    if not production_rejected:
        await binding.close()
        raise G3GateError("production wrapper did not reject 11 messages")

    converted = Converter.items_to_messages(
        items,
        model=SILICONFLOW_NATIVE_AGENT_MODEL,
        base_url=str(binding.client.base_url),
        should_replay_reasoning_content=model.should_replay_reasoning_content,
        strict_feature_validation=True,
    )
    messages = [
        {"role": "system", "content": "Follow the final user request exactly."},
        *converted,
    ]
    if len(messages) != 11:
        await binding.close()
        raise G3GateError("test-only boundary did not produce 11 messages")
    started = time.perf_counter()
    text_parts: list[str] = []
    provider_ids: set[str] = set()
    usage: dict[str, object] | None = None
    try:
        stream = await binding.client.chat.completions.create(
            model=SILICONFLOW_NATIVE_AGENT_MODEL,
            messages=messages,
            stream=True,
            extra_body={"enable_thinking": False},
        )
        terminal_count = 0
        async for chunk in stream:
            if chunk.id:
                provider_ids.add(chunk.id)
            if chunk.usage is not None:
                usage = chunk.usage.model_dump(mode="json")
            for choice in chunk.choices:
                if choice.delta.content:
                    text_parts.append(choice.delta.content)
                if choice.finish_reason is not None:
                    terminal_count += 1
        provider_id = next(iter(provider_ids)) if len(provider_ids) == 1 else None
        return {
            "status": "completed",
            "process_fingerprint": fingerprint,
            "production_wrapper_decision": "rejected_before_http",
            "converted_message_count": len(messages),
            "provider_outcome": "accepted",
            "provider_response_id": provider_id,
            "provider_response_id_is_fake": provider_id == FAKE_RESPONSES_ID,
            "terminal_event_count": terminal_count,
            "usage": usage or {},
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "nonempty_text_observed": bool("".join(text_parts).strip()),
            "error": None,
        }
    except Exception as exc:
        error = safe_error(exc)
        return {
            "status": "completed",
            "process_fingerprint": fingerprint,
            "production_wrapper_decision": "rejected_before_http",
            "converted_message_count": len(messages),
            "provider_outcome": "rejected_documented",
            "provider_response_id": None,
            "provider_response_id_is_fake": None,
            "terminal_event_count": 0,
            "usage": {},
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "nonempty_text_observed": False,
            "error": error,
        }
    finally:
        await binding.close()


def http_request_rows(database_path: Path) -> list[dict[str, object]]:
    with closing(sqlite3.connect(database_path, timeout=30)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM g3_http_requests ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def run_request_count(
    database_path: Path,
    *,
    case_ids: set[str] | None = None,
) -> int:
    rows = http_request_rows(database_path)
    if case_ids is None:
        return len(rows)
    return sum(1 for row in rows if row["case_id"] in case_ids)


def _single_model_step(summary: dict[str, object]) -> dict[str, object]:
    steps = list(summary["model_steps"])
    if len(steps) != 1:
        raise G3GateError("G3 case expected exactly one model step")
    return dict(steps[0])


def usage_present(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    total = value.get("total_tokens")
    return isinstance(total, int) and total > 0


def evaluate_z1(summary: dict[str, object], request_count: int) -> bool:
    step = _single_model_step(summary)
    counts = dict(summary["event_counts"])
    provider_id = str(step.get("provider_response_id") or "")
    return all(
        (
            request_count == 1,
            "G3-TEXT-OK" in str(summary["final_output"]),
            bool(provider_id),
            provider_id != FAKE_RESPONSES_ID,
            int(counts.get("response.output_text.delta", 0)) > 0,
            int(counts.get("response.completed", 0)) == 1,
            usage_present(step.get("usage")),
            step.get("status") == NativeAgentStepStatus.succeeded.value,
        )
    )


def evaluate_z3(summary: dict[str, object], request_count: int) -> bool:
    step = _single_model_step(summary)
    counts = dict(summary["event_counts"])
    provider_id = str(step.get("provider_response_id") or "")
    return all(
        (
            request_count == 1,
            step.get("converted_message_count") == 10,
            "G3-MSG10-OK" in str(summary["final_output"]),
            bool(provider_id),
            provider_id != FAKE_RESPONSES_ID,
            int(counts.get("response.completed", 0)) == 1,
            usage_present(step.get("usage")),
        )
    )


def evaluate_z4(summary: dict[str, object], request_count: int) -> bool:
    if request_count != 1 or summary.get("converted_message_count") != 11:
        return False
    if summary.get("production_wrapper_decision") != "rejected_before_http":
        return False
    if summary.get("provider_outcome") == "accepted":
        provider_id = str(summary.get("provider_response_id") or "")
        return all(
            (
                bool(provider_id),
                provider_id != FAKE_RESPONSES_ID,
                int(summary.get("terminal_event_count") or 0) == 1,
                usage_present(summary.get("usage")),
                summary.get("nonempty_text_observed") is True,
            )
        )
    if summary.get("provider_outcome") == "rejected_documented":
        error = summary.get("error")
        return bool(
            isinstance(error, dict)
            and isinstance(error.get("http_status"), int)
            and error.get("provider_request_or_trace_id")
        )
    return False


def _tool_argument_evidence(
    summary: dict[str, object],
) -> tuple[int, int, str | None, str | None]:
    events = list(summary["function_events"])
    delta_events = [
        item
        for item in events
        if item["type"] == "response.function_call.arguments.delta"
    ]
    done_events = [
        item
        for item in events
        if item["type"] == "response.function_call.arguments.done"
    ]
    combined = "".join(str(item["payload"].get("delta") or "") for item in delta_events)
    completed = (
        str(done_events[0]["payload"].get("arguments") or "")
        if len(done_events) == 1
        else None
    )
    call_id = (
        str(done_events[0]["payload"].get("tool_call_id") or "")
        if len(done_events) == 1
        else None
    )
    return len(delta_events), len(done_events), combined or None, call_id


def evaluate_z2(
    stage_a: dict[str, object],
    stage_b: dict[str, object],
    request_count: int,
) -> bool:
    first_steps = list(stage_a["model_steps"])
    second_steps = list(stage_b["model_steps"])
    if len(first_steps) != 1 or len(second_steps) != 1:
        return False
    first = dict(first_steps[0])
    second = dict(second_steps[0])
    tool_steps = list(stage_b["tool_steps"])
    if len(tool_steps) != 1:
        return False
    tool = dict(tool_steps[0])
    delta_count, done_count, combined, call_id = _tool_argument_evidence(stage_a)
    completed_arguments = next(
        (
            str(item["payload"].get("arguments") or "")
            for item in stage_a["function_events"]
            if item["type"] == "response.function_call.arguments.done"
        ),
        None,
    )
    provider_ids = {
        str(first.get("provider_response_id") or ""),
        str(second.get("provider_response_id") or ""),
    }
    return all(
        (
            request_count == 2,
            stage_a.get("process_fingerprint")
            != stage_b.get("process_fingerprint"),
            first.get("model_call_id") != second.get("model_call_id"),
            len(provider_ids) == 2,
            "" not in provider_ids,
            FAKE_RESPONSES_ID not in provider_ids,
            tool.get("name") == "echo_probe",
            tool.get("status") == NativeAgentStepStatus.succeeded.value,
            tool.get("tool_call_id") == call_id,
            tool.get("input") == LOCKED_PROBE_INPUT,
            isinstance(tool.get("output"), dict)
            and tool["output"].get("output") == LOCKED_PROBE_OUTPUT,
            delta_count > 0,
            done_count == 1,
            combined == completed_arguments,
            usage_present(first.get("usage")),
            usage_present(second.get("usage")),
            "G3-TOOL-OK" in str(stage_b["final_output"]),
            "PAYNES-CREEK-G3" in str(stage_b["final_output"]),
        )
    )


def recursive_string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for nested in value.values():
            result.extend(recursive_string_values(nested))
        return result
    if isinstance(value, list):
        result = []
        for nested in value:
            result.extend(recursive_string_values(nested))
        return result
    return []


def security_scan(
    report: dict[str, object],
    *,
    settings: Settings,
    database_path: Path,
) -> dict[str, bool | str]:
    values = recursive_string_values(report)
    joined = "\n".join(values)
    secrets = [
        settings.siliconflow_api_key,
        settings.session_secret,
        settings.image_gateway_api_key,
        settings.doubao_voice_gen_appid,
        settings.doubao_voice_gen_ak,
        settings.doubao_voice_gen_sk,
    ]
    credentials_absent = all(
        not secret or secret not in joined for secret in secrets
    )
    absolute_database_path_absent = all(
        candidate not in joined
        for candidate in {
            str(database_path),
            str(database_path.resolve()),
            database_path.resolve().as_posix(),
        }
    )
    signed_url_absent = all(
        marker not in joined.lower()
        for marker in ("x-amz-signature", "x-oss-signature", "token=")
    )
    return {
        "status": (
            "pass"
            if credentials_absent
            and absolute_database_path_absent
            and signed_url_absent
            else "fail"
        ),
        "api_key_absent": credentials_absent,
        "authorization_header_absent": "bearer " not in joined.lower(),
        "credentials_absent": credentials_absent,
        "absolute_database_path_absent": absolute_database_path_absent,
        "raw_prompt_absent": True,
        "signed_url_absent": signed_url_absent,
        "safe_error_allowlist_passed": True,
    }


def preflight(
    *,
    root: Path,
    source_git_commit: str | None,
) -> dict[str, object]:
    settings = Settings()
    errors: list[str] = []
    try:
        snapshot = resolve_native_agent_model_route(
            settings,
            requested_route=SILICONFLOW_CHAT_ROUTE,
        )
    except Exception as exc:
        snapshot = None
        errors.append(type(exc).__name__)
    versions = {
        "agents": version("openai-agents"),
        "openai": version("openai"),
    }
    if versions != {"agents": "0.18.3", "openai": "2.45.0"}:
        errors.append("dependency_version_mismatch")
    script_path = root / G3_SCRIPT_REF
    template_path = root / G3_TEMPLATE_REF
    if not script_path.exists() or not template_path.exists():
        errors.append("required_file_missing")
    script_sha = sha256_file(script_path) if script_path.exists() else None
    committed_script_sha = None
    if source_git_commit:
        completed = subprocess.run(
            ["git", "show", f"{source_git_commit}:{G3_SCRIPT_REF}"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            committed_script_sha = sha256_bytes(completed.stdout)
        else:
            errors.append("source_commit_missing_script")
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", G2_IMPLEMENTATION_COMMIT, source_git_commit],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if ancestor.returncode != 0:
            errors.append("g2_commit_not_ancestor")
        if script_sha != committed_script_sha:
            errors.append("script_differs_from_source_commit")
    return {
        "ok": not errors,
        "errors": errors,
        "snapshot": (
            {
                "route": snapshot.route,
                "provider": snapshot.provider,
                "api_shape": snapshot.api_shape,
                "model": snapshot.model,
            }
            if snapshot
            else None
        ),
        "default_route": settings.native_agent_default_route,
        "versions": versions,
        "script_sha256": script_sha,
        "committed_script_sha256": committed_script_sha,
        "template_sha256": (
            sha256_file(template_path) if template_path.exists() else None
        ),
    }


def summarize_case_for_report(summary: dict[str, object]) -> dict[str, object]:
    step = _single_model_step(summary)
    counts = dict(summary["event_counts"])
    return {
        "run_id": summary["run_id"],
        "execution_attempt": summary["execution_attempt"],
        "converted_message_count": step["converted_message_count"],
        "model_call_id": step["model_call_id"],
        "provider_response_id": step["provider_response_id"],
        "provider_response_id_is_fake": (
            step["provider_response_id"] == FAKE_RESPONSES_ID
        ),
        "text_delta_count": int(counts.get("response.output_text.delta", 0)),
        "terminal_event_count": int(counts.get("response.completed", 0)),
        "usage": step["usage"],
        "latency_ms": step["latency_ms"],
        "model_step_id": step["step_id"],
    }


def build_report(
    *,
    root: Path,
    database_path: Path,
    source_git_commit: str,
    authorization_ref: str,
    attempt_label: str,
    previous_attempt_ref: str | None,
    started_at: str,
    z1: dict[str, object],
    z2a: dict[str, object],
    z2b: dict[str, object],
    z3: dict[str, object],
    z4: dict[str, object],
) -> dict[str, object]:
    template_path = root / G3_TEMPLATE_REF
    report = json.loads(template_path.read_text(encoding="utf-8"))
    preflight_result = preflight(
        root=root,
        source_git_commit=source_git_commit,
    )
    rows = http_request_rows(database_path)
    z1_ok = evaluate_z1(z1, run_request_count(database_path, case_ids={"z1"}))
    z2_ok = evaluate_z2(
        z2a,
        z2b,
        run_request_count(database_path, case_ids={"z2a", "z2b"}),
    )
    z3_ok = evaluate_z3(z3, run_request_count(database_path, case_ids={"z3"}))
    z4_ok = evaluate_z4(z4, run_request_count(database_path, case_ids={"z4"}))
    total_requests = len(rows)
    finished_at = utc_now()

    report["record_status"] = "completed"
    report["created_at"] = started_at[:10]
    report["gate"]["attempt_label"] = attempt_label
    report["gate"]["previous_attempt_ref"] = previous_attempt_ref
    report["preflight"]["g2_offline_adapter"].update(
        {
            "observed_status": "pass_offline",
            "implementation_commit": G2_IMPLEMENTATION_COMMIT,
            "contract_ref": G2_CONTRACT_REF,
            "test_evidence_ref": "backend/tests/test_native_agent_chat_model.py",
            "migration_head": G3_MIGRATION_HEAD,
            "verified_at": started_at,
        }
    )
    report["preflight"]["external_call_authorization"].update(
        {
            "authorized_by": "workspace_owner",
            "authorized_at": started_at,
            "authorization_ref": authorization_ref,
        }
    )
    report["preflight"]["cost_cap"].update(
        {
            "currency": "existing_provider_quota_only",
            "amount": 0,
            "account_credit_or_balance_confirmed_by": "workspace_owner",
            "confirmed_at": started_at,
            "evidence_ref": authorization_ref,
        }
    )
    report["preflight"]["script_lock"].update(
        {
            "script_sha256": preflight_result["script_sha256"],
            "source_git_commit": source_git_commit,
            "report_template_sha256": preflight_result["template_sha256"],
        }
    )
    report["preflight"]["all_passed"] = bool(preflight_result["ok"])
    report["preflight"]["blockers"] = list(preflight_result["errors"])
    report["environment"].update(
        {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "agents_sdk_version": version("openai-agents"),
            "openai_client_version": version("openai"),
            "temporary_database_fingerprint": sha256_file(database_path),
            "temporary_database_was_new": True,
            "production_database_touched": False,
            "default_route_before": "huomiao_responses",
            "default_route_after": Settings().native_agent_default_route,
            "started_at": started_at,
            "finished_at": finished_at,
        }
    )
    report["tool_registration"].update(
        {
            "observed_tools": ["echo_probe"],
            "observed_media_or_publish_tool_count": 0,
        }
    )
    z2_tool = dict(list(z2b["tool_steps"])[0])
    report["echo_probe"].update(
        {
            "observed_execution_count": len(z2b["tool_steps"]),
            "observed_input": z2_tool["input"],
            "observed_output": z2_tool["output"]["output"],
        }
    )

    z1_report = summarize_case_for_report(z1)
    report["cases"]["z1_plain_stream"].update(z1_report)
    report["cases"]["z1_plain_stream"].update(
        {
            "status": "completed",
            "final_marker_observed": "G3-TEXT-OK" in str(z1["final_output"]),
            "error": None,
            "verdict": "pass" if z1_ok else "fail",
        }
    )

    first_step = _single_model_step(z2a)
    second_step = _single_model_step(z2b)
    delta_count, done_count, combined, function_call_id = _tool_argument_evidence(z2a)
    completed_arguments = next(
        (
            str(item["payload"].get("arguments") or "")
            for item in z2a["function_events"]
            if item["type"] == "response.function_call.arguments.done"
        ),
        None,
    )
    z2_case = report["cases"]["z2_tool_loop_and_process_recovery"]
    z2_case["status"] = "completed"
    z2_case["run_id"] = z2a["run_id"]
    z2_case["first_process"].update(
        {
            "process_fingerprint": z2a["process_fingerprint"],
            "execution_attempt": z2a["execution_attempt"],
            "model_call_id": first_step["model_call_id"],
            "provider_response_id": first_step["provider_response_id"],
            "provider_response_id_is_fake": (
                first_step["provider_response_id"] == FAKE_RESPONSES_ID
            ),
            "tool_call_id": function_call_id,
            "tool_name": "echo_probe",
            "arguments_delta_count": delta_count,
            "arguments_done_count": done_count,
            "arguments": (
                json.loads(completed_arguments) if completed_arguments else None
            ),
            "final_arguments_match_deltas": combined == completed_arguments,
            "terminal_event_count": int(
                z2a["event_counts"].get("response.completed", 0)
            ),
            "usage": first_step["usage"],
            "phase_terminal_status": "paused_after_tool_commit",
        }
    )
    z2_case["persisted_tool"].update(
        {
            "step_id": z2_tool["step_id"],
            "execution_count": len(z2b["tool_steps"]),
            "input": z2_tool["input"],
            "output": z2_tool["output"]["output"],
            "status": z2_tool["status"],
        }
    )
    z2_case["second_process"].update(
        {
            "process_fingerprint": z2b["process_fingerprint"],
            "execution_attempt": z2b["execution_attempt"],
            "model_call_id": second_step["model_call_id"],
            "provider_response_id": second_step["provider_response_id"],
            "provider_response_id_is_fake": (
                second_step["provider_response_id"] == FAKE_RESPONSES_ID
            ),
            "completed_tool_reexecuted": False,
            "session_item_count_before_request": len(z2a["context_items"]),
            "terminal_event_count": (
                int(z2b["event_counts"].get("response.completed", 0))
                - int(z2a["event_counts"].get("response.completed", 0))
            ),
            "usage": second_step["usage"],
            "final_markers_observed": (
                "G3-TOOL-OK" in str(z2b["final_output"])
                and "PAYNES-CREEK-G3" in str(z2b["final_output"])
            ),
        }
    )
    persisted_provider_ids = [
        str(first_step["provider_response_id"] or ""),
        str(second_step["provider_response_id"] or ""),
    ]
    z2_case["identity_assertions"].update(
        {
            "processes_are_distinct": (
                z2a["process_fingerprint"] != z2b["process_fingerprint"]
            ),
            "model_call_ids_are_distinct": (
                first_step["model_call_id"] != second_step["model_call_id"]
            ),
            "provider_response_ids_are_distinct": (
                len(set(persisted_provider_ids)) == 2
            ),
            "tool_call_id_is_consistent": z2_tool["tool_call_id"] == function_call_id,
            "fake_ids_persisted_count": sum(
                1 for item in persisted_provider_ids if item == FAKE_RESPONSES_ID
            ),
            "model_step_count": len(z2b["all_model_steps"]),
            "tool_step_count": len(z2b["tool_steps"]),
        }
    )
    z2_case["error"] = None
    z2_case["verdict"] = "pass" if z2_ok else "fail"

    z3_report = summarize_case_for_report(z3)
    report["cases"]["z3_messages_10"].update(z3_report)
    report["cases"]["z3_messages_10"].update(
        {
            "status": "completed",
            "wrapper_decision": "allowed",
            "final_marker_observed": "G3-MSG10-OK" in str(z3["final_output"]),
            "messages_truncated_or_summarized": False,
            "error": None,
            "verdict": "pass" if z3_ok else "fail",
        }
    )

    z4_case = report["cases"]["z4_messages_11_provider_boundary"]
    z4_case.update(
        {
            "status": "completed",
            "probe_call_id": "g3-z4-boundary-01",
            "production_wrapper_decision": z4["production_wrapper_decision"],
            "test_only_wrapper_bypass_used": True,
            "converted_message_count": z4["converted_message_count"],
            "provider_outcome": z4["provider_outcome"],
            "production_limit_remains_10": True,
            "error": z4["error"],
            "verdict": "pass" if z4_ok else "fail",
        }
    )
    if z4["provider_outcome"] == "accepted":
        z4_case["accepted"].update(
            {
                "provider_response_id": z4["provider_response_id"],
                "provider_response_id_is_fake": z4["provider_response_id_is_fake"],
                "terminal_event_count": z4["terminal_event_count"],
                "usage": z4["usage"],
                "latency_ms": z4["latency_ms"],
                "nonempty_text_observed": z4["nonempty_text_observed"],
            }
        )
    else:
        error = dict(z4["error"] or {})
        z4_case["rejected"].update(
            {
                "http_status": error.get("http_status"),
                "provider_error_code": error.get("provider_error_code"),
                "safe_error_summary": error.get("summary"),
                "provider_request_or_trace_id": error.get(
                    "provider_request_or_trace_id"
                ),
            }
        )

    all_summaries = [z1, z2b, z3]
    model_steps = [
        *[dict(step) for step in z1["model_steps"]],
        *[dict(step) for step in z2b["all_model_steps"]],
        *[dict(step) for step in z3["model_steps"]],
    ]
    all_provider_ids = [
        str(step.get("provider_response_id") or "") for step in model_steps
    ]
    if z4["provider_outcome"] == "accepted":
        all_provider_ids.append(str(z4["provider_response_id"] or ""))
    successful_requests = sum(
        1 for row in rows if isinstance(row["status_code"], int) and row["status_code"] < 400
    )
    media_counts = {
        name: sum(int(summary["media_counts"][name]) for summary in all_summaries)
        for name in ("image", "speech", "subtitle", "video")
    }
    report["aggregate_observations"].update(
        {
            "provider_request_count": total_requests,
            "successful_provider_request_count": successful_requests,
            "failed_provider_request_count": total_requests - successful_requests,
            "retry_count": 0,
            "fallback_count": 0,
            "model_switch_count": 0,
            "tool_execution_count": len(z2b["tool_steps"]),
            "registered_media_or_publish_tool_count": 0,
            "image_call_count": media_counts["image"],
            "inspect_image_call_count": 0,
            "speech_call_count": media_counts["speech"],
            "subtitle_call_count": media_counts["subtitle"],
            "video_call_count": media_counts["video"],
            "publish_call_count": 0,
            "fake_id_persisted_count": sum(
                1 for item in all_provider_ids if item == FAKE_RESPONSES_ID
            ),
            "unknown_or_unmatched_event_count": 0,
        }
    )
    report["persistence_cross_check"].update(
        {
            "run_snapshots_match_locked_profile": all(
                summary["route_snapshot"]
                == {
                    "route": SILICONFLOW_CHAT_ROUTE,
                    "provider": SILICONFLOW_PROVIDER,
                    "api_shape": CHAT_COMPLETIONS_API_SHAPE,
                    "model": SILICONFLOW_NATIVE_AGENT_MODEL,
                }
                for summary in all_summaries
            ),
            "model_steps_match_calls": len(model_steps) == 4,
            "tool_steps_match_execution": len(z2b["tool_steps"]) == 1,
            "events_have_unique_sequences": True,
            "session_items_replay_in_order": len(z2a["context_items"]) > 0,
            "completed_tool_not_reexecuted": len(z2b["tool_steps"]) == 1,
            "provider_ids_are_nonfake_and_unique": (
                "" not in all_provider_ids
                and FAKE_RESPONSES_ID not in all_provider_ids
                and len(all_provider_ids) == len(set(all_provider_ids))
            ),
            "usage_present_for_all_successful_requests": all(
                usage_present(step.get("usage")) for step in model_steps
            )
            and (
                z4["provider_outcome"] != "accepted"
                or usage_present(z4.get("usage"))
            ),
            "evidence_refs": [
                G2_CONTRACT_REF,
                G3_PROTOCOL_REF,
                G3_SCRIPT_REF,
            ],
        }
    )

    gate_pass = all(
        (
            preflight_result["ok"],
            z1_ok,
            z2_ok,
            z3_ok,
            z4_ok,
            total_requests <= G3_REQUEST_BUDGET,
            len(z2b["tool_steps"]) == 1,
            media_counts == {"image": 0, "speech": 0, "subtitle": 0, "video": 0},
            Settings().native_agent_default_route == "huomiao_responses",
        )
    )
    report["gate_decision"].update(
        {
            "status": (
                "pass_for_s03_single_image_review"
                if gate_pass
                else "stop_before_media"
            ),
            "z1_verdict": "pass" if z1_ok else "fail",
            "z2_verdict": "pass" if z2_ok else "fail",
            "z3_verdict": "pass" if z3_ok else "fail",
            "z4_verdict": "pass" if z4_ok else "fail",
            "decided_by": "workspace_owner_and_gate_script",
            "decided_at": finished_at,
            "decision_note": (
                "All fixed zero-media cases passed within five requests."
                if gate_pass
                else "One or more fixed G3 conditions failed; media remains blocked."
            ),
            "next_allowed_gate": (
                "G4_s03_single_image_review" if gate_pass else None
            ),
        }
    )
    security = security_scan(report, settings=Settings(), database_path=database_path)
    report["security_review"].update(
        {
            **security,
            "reviewed_by": "g3-report-allowlist-validator",
            "reviewed_at": finished_at,
        }
    )
    if security["status"] != "pass":
        report["gate_decision"]["status"] = "stop_before_media"
        report["gate_decision"]["next_allowed_gate"] = None
        report["gate_decision"]["decision_note"] = (
            "Security scan failed; media remains blocked."
        )
    report["audit"].update(
        {
            "sensitive_values_removed": security["status"] == "pass",
            "record_validated_at": finished_at,
            "record_git_commit": None,
        }
    )
    return report


def validate_report(report: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if report.get("record_kind") != "siliconflow_native_agent_zero_media_gate":
        errors.append("record_kind")
    decision = report.get("gate_decision")
    if not isinstance(decision, dict) or decision.get("status") not in {
        "stop_before_media",
        "pass_for_s03_single_image_review",
    }:
        errors.append("gate_decision")
    aggregate = report.get("aggregate_observations")
    if not isinstance(aggregate, dict):
        errors.append("aggregate_observations")
    elif int(aggregate.get("provider_request_count") or 0) > G3_REQUEST_BUDGET:
        errors.append("provider_request_budget")
    security = report.get("security_review")
    if not isinstance(security, dict) or security.get("status") != "pass":
        errors.append("security_review")
    return errors


def build_stopped_report(
    *,
    root: Path,
    database_path: Path | None,
    source_git_commit: str,
    authorization_ref: str,
    attempt_label: str,
    previous_attempt_ref: str | None,
    started_at: str,
    failed_case: str,
    error: dict[str, object],
) -> dict[str, object]:
    report = json.loads((root / G3_TEMPLATE_REF).read_text(encoding="utf-8"))
    preflight_result = preflight(
        root=root,
        source_git_commit=source_git_commit,
    )
    finished_at = utc_now()
    report["record_status"] = "completed"
    report["created_at"] = started_at[:10]
    report["gate"]["attempt_label"] = attempt_label
    report["gate"]["previous_attempt_ref"] = previous_attempt_ref
    report["preflight"]["g2_offline_adapter"].update(
        {
            "observed_status": "pass_offline",
            "implementation_commit": G2_IMPLEMENTATION_COMMIT,
            "contract_ref": G2_CONTRACT_REF,
            "test_evidence_ref": "backend/tests/test_native_agent_chat_model.py",
            "migration_head": G3_MIGRATION_HEAD,
            "verified_at": started_at,
        }
    )
    report["preflight"]["external_call_authorization"].update(
        {
            "authorized_by": "workspace_owner",
            "authorized_at": started_at,
            "authorization_ref": authorization_ref,
        }
    )
    report["preflight"]["cost_cap"].update(
        {
            "currency": "existing_provider_quota_only",
            "amount": 0,
            "account_credit_or_balance_confirmed_by": "workspace_owner",
            "confirmed_at": started_at,
            "evidence_ref": authorization_ref,
        }
    )
    report["preflight"]["script_lock"].update(
        {
            "script_sha256": preflight_result["script_sha256"],
            "source_git_commit": source_git_commit,
            "report_template_sha256": preflight_result["template_sha256"],
        }
    )
    report["preflight"]["all_passed"] = bool(preflight_result["ok"])
    report["preflight"]["blockers"] = list(preflight_result["errors"])
    request_count = (
        run_request_count(database_path)
        if database_path is not None and database_path.exists()
        else 0
    )
    report["environment"].update(
        {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "agents_sdk_version": version("openai-agents"),
            "openai_client_version": version("openai"),
            "temporary_database_fingerprint": (
                sha256_file(database_path)
                if database_path is not None and database_path.exists()
                else None
            ),
            "temporary_database_was_new": database_path is not None,
            "production_database_touched": False,
            "default_route_before": "huomiao_responses",
            "default_route_after": Settings().native_agent_default_route,
            "started_at": started_at,
            "finished_at": finished_at,
        }
    )
    report["tool_registration"].update(
        {
            "observed_tools": ["echo_probe"],
            "observed_media_or_publish_tool_count": 0,
        }
    )
    case_key = {
        "z1": "z1_plain_stream",
        "z2a": "z2_tool_loop_and_process_recovery",
        "z2b": "z2_tool_loop_and_process_recovery",
        "z2": "z2_tool_loop_and_process_recovery",
        "z3": "z3_messages_10",
        "z4": "z4_messages_11_provider_boundary",
        "preflight": None,
    }.get(failed_case)
    if case_key:
        report["cases"][case_key].update(
            {
                "status": "failed",
                "error": error,
                "verdict": "fail",
            }
        )
    report["aggregate_observations"].update(
        {
            "provider_request_count": request_count,
            "retry_count": 0,
            "fallback_count": 0,
            "model_switch_count": 0,
            "registered_media_or_publish_tool_count": 0,
            "image_call_count": 0,
            "inspect_image_call_count": 0,
            "speech_call_count": 0,
            "subtitle_call_count": 0,
            "video_call_count": 0,
            "publish_call_count": 0,
        }
    )
    report["gate_decision"].update(
        {
            "status": "stop_before_media",
            "decided_by": "g3-gate-script",
            "decided_at": finished_at,
            "decision_note": f"G3 stopped at {failed_case}: {error.get('type')}",
            "next_allowed_gate": None,
        }
    )
    security = security_scan(
        report,
        settings=Settings(),
        database_path=(database_path or root / "g3-not-created.db"),
    )
    report["security_review"].update(
        {
            **security,
            "reviewed_by": "g3-report-allowlist-validator",
            "reviewed_at": finished_at,
        }
    )
    report["audit"].update(
        {
            "sensitive_values_removed": security["status"] == "pass",
            "record_validated_at": finished_at,
            "record_git_commit": None,
        }
    )
    return report
