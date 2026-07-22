#!/usr/bin/env python3
"""Run a real two-turn Agent Runtime conversation against a temporary database."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core import database  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.models.entities import AgentConversation, AgentMessage, AgentRun, AgentStep, User, new_id  # noqa: E402
from app.models.enums import AgentMessageRole, AgentRunStatus, AgentStepType  # noqa: E402
from app.services.agent_runner import process_agent_run  # noqa: E402


CONTEXT_MARKER = "RUNTIME_CONTEXT_7C91"


def create_turn(session_factory, conversation_id: str, content: str) -> str:
    with session_factory() as db:
        latest = db.scalar(
            select(AgentMessage)
            .where(AgentMessage.conversation_id == conversation_id)
            .order_by(AgentMessage.sequence.desc())
            .limit(1)
        )
        turn_id = new_id()
        run = AgentRun(
            conversation_id=conversation_id,
            turn_id=turn_id,
            status=AgentRunStatus.queued,
        )
        db.add_all(
            [
                AgentMessage(
                    conversation_id=conversation_id,
                    turn_id=turn_id,
                    role=AgentMessageRole.user,
                    content=content,
                    sequence=(latest.sequence + 1) if latest else 1,
                ),
                run,
            ]
        )
        db.commit()
        return run.id


async def run_smoke(output: Path | None) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="doodlestory-agent-runtime-") as temporary_directory:
        engine = create_engine(
            f"sqlite:///{Path(temporary_directory) / 'runtime.db'}",
            connect_args={"check_same_thread": False},
        )
        session_factory = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)
        original_session_factory = database.SessionLocal
        database.SessionLocal = session_factory
        try:
            with session_factory() as db:
                user = User(email="agent-runtime-smoke@example.com", password_hash="not-used")
                conversation = AgentConversation(owner=user, title="Agent Runtime 两轮真实探测")
                db.add_all([user, conversation])
                db.commit()
                conversation_id = conversation.id

            first_run_id = create_turn(
                session_factory,
                conversation_id,
                f"请记住代码 {CONTEXT_MARKER}，并回复你已经记住它。",
            )
            await process_agent_run(first_run_id)
            second_run_id = create_turn(
                session_factory,
                conversation_id,
                "上一轮让我记住的代码是什么？请原样回复代码。",
            )
            await process_agent_run(second_run_id)

            with session_factory() as db:
                runs = db.scalars(
                    select(AgentRun)
                    .where(AgentRun.id.in_([first_run_id, second_run_id]))
                    .order_by(AgentRun.created_at.asc())
                ).all()
                # turn_id and run_id intentionally differ, so query through the Run.
                second_run = db.get(AgentRun, second_run_id)
                second_answer = None
                if second_run is not None:
                    second_answer = db.scalar(
                        select(AgentMessage).where(
                            AgentMessage.conversation_id == conversation_id,
                            AgentMessage.turn_id == second_run.turn_id,
                            AgentMessage.role == AgentMessageRole.assistant,
                        )
                    )
                steps = db.scalars(
                    select(AgentStep)
                    .where(
                        AgentStep.run_id.in_([first_run_id, second_run_id]),
                        AgentStep.step_type == AgentStepType.model_call,
                    )
                    .order_by(AgentStep.created_at.asc())
                ).all()
                message_count = len(
                    db.scalars(
                        select(AgentMessage).where(AgentMessage.conversation_id == conversation_id)
                    ).all()
                )

            if len(runs) != 2 or any(run.status != AgentRunStatus.succeeded for run in runs):
                raise RuntimeError("Two-turn Agent Runtime smoke did not finish both Runs")
            if second_answer is None or CONTEXT_MARKER not in second_answer.content:
                raise RuntimeError("Second Agent turn did not use the first turn application history")
            report: dict[str, object] = {
                "schema_version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "pass",
                "model": "gpt-5.6-terra",
                "api_shape": "responses",
                "context": {
                    "source": "application_database",
                    "uses_previous_response_id": False,
                    "second_turn_marker_verified": True,
                },
                "conversation_id": conversation_id,
                "run_ids": [first_run_id, second_run_id],
                "message_count": message_count,
                "model_steps": [
                    {
                        "step_id": step.id,
                        "run_id": step.run_id,
                        "provider": step.provider,
                        "model": step.model,
                        "api_shape": step.api_shape,
                        "attempt": step.attempt,
                        "provider_request_id": step.provider_request_id,
                        "status": step.status.value,
                    }
                    for step in steps
                ],
            }
        finally:
            database.SessionLocal = original_session_factory
            engine.dispose()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional redacted JSON report path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    asyncio.run(run_smoke(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
