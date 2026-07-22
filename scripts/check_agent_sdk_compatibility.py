#!/usr/bin/env python3
"""Probe the Agents SDK Responses tool loop on each Agent V1 provider.

Every selected provider is called independently. The probe disables SDK/client
retries, never falls back across providers, never writes response bodies, and
redacts configured API keys from diagnostic errors.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from openai import AsyncOpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agents import Agent, ModelSettings, RunConfig, Runner, function_tool  # noqa: E402
from agents.model_settings import ModelRetrySettings  # noqa: E402
from agents.models.openai_provider import OpenAIProvider  # noqa: E402
from app.core.config import get_settings  # noqa: E402


EXPECTED_TOOL_VALUE = "SDK_TOOL_OUTPUT_OK"
EXPECTED_FIRST_TURN_MARKER = "SDK_TOOL_LOOP_OK"
EXPECTED_REPLAY_MARKER = "SDK_APPLICATION_REPLAY_OK"
MAX_ERROR_CHARS = 800


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str

    @property
    def host(self) -> str:
        return urlparse(self.base_url).netloc


def redact_text(text: str, secrets: list[str] | tuple[str, ...] = ()) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;\"'}]+",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+",
        r"\1[REDACTED]",
        redacted,
    )
    return redacted[:MAX_ERROR_CHARS]


def load_provider_configs(model: str) -> dict[str, ProviderConfig]:
    settings = get_settings()
    return {
        "huomiao": ProviderConfig(
            name="huomiao",
            base_url=settings.text_fallback_openai_base_url,
            api_key=settings.text_fallback_api_key.strip(),
            model=model,
        ),
        "lio": ProviderConfig(
            name="lio",
            base_url=settings.lio_openai_base_url,
            api_key=settings.lio_api_key.strip(),
            model=model,
        ),
    }


def build_openai_provider(
    config: ProviderConfig,
    *,
    timeout_seconds: float,
) -> OpenAIProvider:
    client = AsyncOpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        max_retries=0,
        timeout=timeout_seconds,
    )
    return OpenAIProvider(openai_client=client, use_responses=True)


def summarize_usage(raw_responses: list[Any]) -> dict[str, int]:
    totals = {
        "requests": len(raw_responses),
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    for response in raw_responses:
        usage = getattr(response, "usage", None)
        if usage is None:
            continue
        totals["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
        totals["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
        totals["total_tokens"] += int(getattr(usage, "total_tokens", 0) or 0)
    return totals


async def probe_provider(
    config: ProviderConfig,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    missing = [
        name
        for name, value in (
            ("base_url", config.base_url),
            ("api_key", config.api_key),
            ("model", config.model),
        )
        if not value
    ]
    if missing:
        return {
            "provider": config.name,
            "host": config.host,
            "model": config.model or None,
            "status": "fail",
            "latency_ms": 0,
            "error": f"Missing required fields: {', '.join(missing)}",
        }

    tool_calls: list[str] = []

    @function_tool
    def read_compatibility_token(token_name: str) -> str:
        """Return the fixed compatibility value for the requested token name."""

        tool_calls.append(token_name)
        return EXPECTED_TOOL_VALUE

    agent = Agent(
        name="DoodleStory Agent SDK Compatibility Probe",
        instructions=(
            "This is a deterministic compatibility check. On the first user turn, "
            "call read_compatibility_token exactly once with token_name=agent-v1. "
            f"After the tool result, reply with {EXPECTED_FIRST_TURN_MARKER}: "
            f"followed by the exact tool value. On the next user turn, use the "
            "replayed application history and reply with only "
            f"{EXPECTED_REPLAY_MARKER}."
        ),
        model=config.model,
        model_settings=ModelSettings(
            tool_choice="required",
            parallel_tool_calls=False,
            retry=ModelRetrySettings(max_retries=0),
        ),
        tools=[read_compatibility_token],
    )
    provider = build_openai_provider(
        config,
        timeout_seconds=timeout_seconds,
    )
    run_config = RunConfig(
        model_provider=provider,
        tracing_disabled=True,
        workflow_name="DoodleStory Agent SDK Compatibility Probe",
    )
    started = time.perf_counter()
    try:
        first_result = await Runner.run(
            agent,
            (
                "Run the required compatibility tool now. Do not answer before "
                "using the tool."
            ),
            run_config=run_config,
            max_turns=4,
        )
        first_output = str(first_result.final_output or "").strip()
        if tool_calls != ["agent-v1"]:
            raise RuntimeError(
                "SDK tool loop did not execute the expected single function call"
            )
        if EXPECTED_FIRST_TURN_MARKER not in first_output:
            raise RuntimeError("SDK tool loop final answer is missing the marker")
        if EXPECTED_TOOL_VALUE not in first_output:
            raise RuntimeError("SDK tool output was not carried into the final answer")

        replay_input = first_result.to_input_list(mode="normalized")
        replay_input.append(
            {
                "role": "user",
                "content": (
                    "This is the application replay turn. Do not call a tool. "
                    f"Reply with only {EXPECTED_REPLAY_MARKER}."
                ),
            }
        )
        replay_agent = Agent(
            name=agent.name,
            instructions=agent.instructions,
            model=config.model,
            model_settings=ModelSettings(
                retry=ModelRetrySettings(max_retries=0),
            ),
            tools=[read_compatibility_token],
        )
        second_result = await Runner.run(
            replay_agent,
            replay_input,
            run_config=run_config,
            max_turns=2,
        )
        second_output = str(second_result.final_output or "").strip()
        if second_output != EXPECTED_REPLAY_MARKER:
            raise RuntimeError("Application-side full input replay did not pass")
        if tool_calls != ["agent-v1"]:
            raise RuntimeError("Application replay unexpectedly executed another tool")
    except Exception as exc:
        return {
            "provider": config.name,
            "host": config.host,
            "model": config.model,
            "status": "fail",
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "error_type": type(exc).__name__,
            "error": redact_text(str(exc), [config.api_key]),
        }
    finally:
        await provider._client.close()

    all_responses = list(first_result.raw_responses) + list(second_result.raw_responses)
    request_ids = [
        response.request_id
        for response in all_responses
        if getattr(response, "request_id", None)
    ]
    return {
        "provider": config.name,
        "host": config.host,
        "model": config.model,
        "api_shape": "responses",
        "status": "pass",
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "tool_loop": {
            "function_call_count": len(tool_calls),
            "tool_output_observed_in_final": True,
        },
        "application_replay": {
            "uses_previous_response_id": False,
            "replayed_item_count": len(replay_input) - 1,
            "second_turn_passed": True,
        },
        "usage": summarize_usage(all_responses),
        "provider_request_ids": request_ids,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=("all", "huomiao", "lio"),
        default="all",
        help="Provider to probe independently (default: all)",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.5",
        help="Exact model to test on every provider",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Timeout for each SDK request; retries remain disabled",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    return parser


async def async_main() -> int:
    args = build_parser().parse_args()
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be greater than zero")
    if not args.model.strip():
        raise SystemExit("--model must not be empty")

    configs = load_provider_configs(args.model.strip())
    provider_names = list(configs) if args.provider == "all" else [args.provider]
    providers = [
        await probe_provider(
            configs[provider_name],
            timeout_seconds=args.timeout_seconds,
        )
        for provider_name in provider_names
    ]
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sdk": {
            "openai_agents": importlib.metadata.version("openai-agents"),
            "openai": importlib.metadata.version("openai"),
        },
        "probe_policy": {
            "api_shape": "responses",
            "client_retry_attempts": 0,
            "sdk_retry_attempts": 0,
            "cross_provider_fallback": False,
            "application_history_replay": True,
        },
        "providers": providers,
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    return 1 if any(item["status"] != "pass" for item in providers) else 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
