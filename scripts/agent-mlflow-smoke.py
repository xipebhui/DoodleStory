#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core import database  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.models.entities import (  # noqa: E402
    AgentConversation,
    AgentMessage,
    AgentRun,
    User,
    new_id,
)
from app.models.enums import AgentMessageRole, AgentRunStatus  # noqa: E402
from app.services.agent_model_router import AgentModelRouter  # noqa: E402
from app.services.agent_observability import (  # noqa: E402
    initialize_agent_observability,
)
from app.services.agent_runner import process_agent_run  # noqa: E402


class InjectedProviderError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class SmokeRouter(AgentModelRouter):
    def __init__(self, scenario: str):
        super().__init__()
        self.scenario = scenario

    async def _invoke(self, config, route, input_items):
        if route.provider == "huomiao" and self.scenario == "fallback_success":
            raise InjectedProviderError(503, "upstream temporarily unavailable")
        if route.provider == "huomiao" and self.scenario == "permanent_error":
            raise InjectedProviderError(503, "no available channel for model")
        return await super()._invoke(config, route, input_items)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="创建受控 Agent Turn，并按 agent_run_id 查询 MLflow trace。",
    )
    parser.add_argument("--owner-email", required=True)
    parser.add_argument(
        "--scenario",
        choices=("primary_success", "fallback_success", "permanent_error"),
        default="primary_success",
    )
    return parser.parse_args()


def create_controlled_run(owner_email: str, scenario: str) -> str:
    with database.SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == owner_email.strip().lower()))
        if user is None:
            raise RuntimeError("指定 owner-email 不存在")
        conversation = AgentConversation(
            owner_user_id=user.id,
            title=f"MLflow smoke: {scenario}",
        )
        turn_id = new_id()
        message = AgentMessage(
            conversation=conversation,
            turn_id=turn_id,
            role=AgentMessageRole.user,
            content="这是受控可观测性测试，请只回复：观测测试完成。",
            resource_refs_json="[]",
            sequence=1,
        )
        run = AgentRun(
            conversation=conversation,
            turn_id=turn_id,
            status=AgentRunStatus.queued,
        )
        db.add_all([conversation, message, run])
        db.commit()
        return run.id


def query_trace(agent_run_id: str) -> dict[str, object]:
    import mlflow

    settings = get_settings()
    mlflow.flush_trace_async_logging()
    experiment = mlflow.get_experiment_by_name(settings.mlflow_experiment_name)
    if experiment is None:
        raise RuntimeError("找不到已配置的 MLflow experiment")
    traces = mlflow.search_traces(
        locations=[experiment.experiment_id],
        filter_string=f"tags.agent_run_id = '{agent_run_id}'",
        return_type="list",
        include_spans=True,
        flush=True,
    )
    if len(traces) != 1:
        raise RuntimeError(f"agent_run_id 应匹配唯一 trace，实际为 {len(traces)} 条")
    trace = traces[0]
    model_spans = [span for span in trace.data.spans if span.name == "agent.model_call"]
    providers = [span.attributes.get("provider") for span in model_spans]
    models = [span.attributes.get("model") for span in model_spans]
    return {
        "agent_run_id": agent_run_id,
        "root_trace_found": any(span.name == "agent.run" for span in trace.data.spans),
        "trace_id": trace.info.trace_id,
        "span_count": len(trace.data.spans),
        "providers": providers,
        "models": models,
        "fallback": any(span.attributes.get("fallback_from") for span in model_spans),
        "query": f"tags.agent_run_id = '{agent_run_id}'",
    }


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    if not settings.mlflow_tracing_enabled:
        raise RuntimeError("请先设置 MLFLOW_TRACING_ENABLED=true")
    initialize_agent_observability(settings)
    run_id = create_controlled_run(args.owner_email, args.scenario)
    await process_agent_run(run_id, router=SmokeRouter(args.scenario))
    result = query_trace(run_id)
    with database.SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        result["run_status"] = run.status.value
        result["error_code"] = run.error_code
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
