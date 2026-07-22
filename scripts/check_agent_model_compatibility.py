#!/usr/bin/env python3
"""Probe OpenAI-compatible model gateways for Agent V1 capabilities.

The probe deliberately calls each provider independently and performs no retry or
cross-provider fallback. Its output is safe to keep as compatibility evidence:
API keys and raw response bodies are never included in successful results, while
failure snippets are redacted and truncated.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import struct
import sys
import time
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402


CAPABILITY_NAMES = ("chat", "structured", "tools", "multimodal", "responses")
RETRYABLE_HTTP_STATUSES = {408, 409, 429, 500, 502, 503, 504}
MAX_ERROR_CHARS = 600


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str

    @property
    def host(self) -> str:
        return urlparse(self.base_url).netloc


class CapabilityFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        response_text: str = "",
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.response_text = response_text


def redact_text(text: str, secrets: list[str] | tuple[str, ...] = ()) -> str:
    """Remove configured keys and common Authorization header representations."""

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


def is_retryable_failure(
    *,
    status_code: int | None = None,
    exception: BaseException | None = None,
    response_text: str = "",
) -> bool:
    """Return the retry classification proposed for the future model router."""

    if isinstance(exception, (requests.Timeout, requests.ConnectionError)):
        return True
    normalized_error = response_text.lower().replace(" ", "")
    permanent_error_markers = (
        "invalid_request",
        "notsupported",
        "unsupported",
        "doesnotsupport",
        "不支持此api路径",
    )
    if any(marker in normalized_error for marker in permanent_error_markers):
        return False
    return status_code in RETRYABLE_HTTP_STATUSES


def extract_chat_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                fragments.append(text)
        return "".join(fragments).strip()
    return ""


def extract_responses_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    fragments: list[str] = []
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                fragments.append(text)
    return "".join(fragments).strip()


def _solid_red_png_data_url(width: int = 32, height: int = 32) -> str:
    """Build a tiny deterministic PNG without adding an image dependency."""

    signature = b"\x89PNG\r\n\x1a\n"

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        body = chunk_type + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    scanline = b"\x00" + (b"\xff\x00\x00" * width)
    raw_pixels = scanline * height
    png = (
        signature
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw_pixels))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


class ProviderProbe:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        timeout_seconds: float,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            response = self.session.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "DoodleStory-Agent-Compatibility-Probe/1.0",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise CapabilityFailure(
                f"{type(exc).__name__}: {exc}",
                response_text=str(exc),
            ) from exc

        if not 200 <= response.status_code < 300:
            raise CapabilityFailure(
                f"HTTP {response.status_code}",
                http_status=response.status_code,
                response_text=response.text,
            )
        try:
            parsed = response.json()
        except ValueError as exc:
            raise CapabilityFailure(
                "Response body is not valid JSON",
                http_status=response.status_code,
                response_text=response.text,
            ) from exc
        if not isinstance(parsed, dict):
            raise CapabilityFailure(
                "Response JSON root is not an object",
                http_status=response.status_code,
            )
        return parsed

    def check_chat(self) -> str:
        payload = self._post(
            "chat/completions",
            {
                "model": self.config.model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Compatibility check. Reply with only CHAT_OK.",
                    }
                ],
            },
        )
        content = extract_chat_text(payload)
        if "CHAT_OK" not in content.upper():
            raise CapabilityFailure("Chat response did not contain the expected marker")
        return "Chat Completions returned the expected marker"

    def check_structured(self) -> str:
        payload = self._post(
            "chat/completions",
            {
                "model": self.config.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": "Return one valid JSON object and no markdown.",
                    },
                    {
                        "role": "user",
                        "content": (
                            'Return a JSON object with exactly two keys: "status" must be '
                            'the string "ok", and "panel_count" must be the integer 5. '
                            "Do not rename, translate, summarize, wrap, or omit either key."
                        ),
                    },
                ],
            },
        )
        content = extract_chat_text(payload)
        try:
            structured = json.loads(content)
        except json.JSONDecodeError as exc:
            raise CapabilityFailure("Structured response content is not valid JSON") from exc
        if structured.get("status") != "ok" or structured.get("panel_count") != 5:
            raise CapabilityFailure("Structured response did not preserve required fields")
        return "JSON mode returned parseable required fields"

    def check_tools(self) -> str:
        tool = {
            "type": "function",
            "function": {
                "name": "get_panel_status",
                "description": "Read the current generation status of one comic panel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "panel_index": {"type": "integer", "minimum": 1}
                    },
                    "required": ["panel_index"],
                    "additionalProperties": False,
                },
            },
        }
        first_payload = self._post(
            "chat/completions",
            {
                "model": self.config.model,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Use get_panel_status for panel 3. After receiving the tool "
                            "result, report whether the panel is complete."
                        ),
                    }
                ],
                "tools": [tool],
                "tool_choice": {
                    "type": "function",
                    "function": {"name": "get_panel_status"},
                },
            },
        )
        choices = first_payload.get("choices")
        message = choices[0].get("message") if isinstance(choices, list) and choices else None
        tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
        if not isinstance(tool_calls, list) or not tool_calls:
            raise CapabilityFailure("Model did not return a function tool call")
        first_call = tool_calls[0]
        function = first_call.get("function") if isinstance(first_call, dict) else None
        if not isinstance(function, dict) or function.get("name") != "get_panel_status":
            raise CapabilityFailure("Model returned an unexpected function name")
        try:
            arguments = json.loads(function.get("arguments", ""))
        except (TypeError, json.JSONDecodeError) as exc:
            raise CapabilityFailure("Function arguments are not valid JSON") from exc
        if arguments.get("panel_index") != 3:
            raise CapabilityFailure("Function arguments did not target panel 3")
        tool_call_id = first_call.get("id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            raise CapabilityFailure("Function tool call did not include an id")

        assistant_tool_call = {
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": "get_panel_status",
                "arguments": function["arguments"],
            },
        }
        second_payload = self._post(
            "chat/completions",
            {
                "model": self.config.model,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Use get_panel_status for panel 3. After receiving the tool "
                            "result, report whether the panel is complete."
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [assistant_tool_call],
                    },
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(
                            {"panel_index": 3, "status": "completed"},
                            ensure_ascii=False,
                        ),
                    },
                ],
                "tools": [tool],
                "tool_choice": "auto",
            },
        )
        final_content = extract_chat_text(second_payload)
        if not final_content:
            raise CapabilityFailure("Model did not produce text after the tool result")
        return "Function call and follow-up tool-result turn both succeeded"

    def check_multimodal(self) -> str:
        payload = self._post(
            "chat/completions",
            {
                "model": self.config.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "What is the dominant color? Answer with one word.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": _solid_red_png_data_url()},
                            },
                        ],
                    }
                ],
            },
        )
        content = extract_chat_text(payload)
        if not content:
            raise CapabilityFailure("Multimodal request returned no text")
        return "Chat Completions accepted an inline PNG and returned text"

    def check_responses(self) -> str:
        payload = self._post(
            "responses",
            {
                "model": self.config.model,
                "input": "Compatibility check. Reply with only RESPONSES_OK.",
                "max_output_tokens": 64,
            },
        )
        content = extract_responses_text(payload)
        if "RESPONSES_OK" not in content.upper():
            raise CapabilityFailure("Responses API output did not contain expected marker")
        return "Responses API returned the expected marker"

    def run_capability(self, capability: str) -> dict[str, Any]:
        checker: Callable[[], str] = getattr(self, f"check_{capability}")
        started = time.perf_counter()
        try:
            evidence = checker()
        except CapabilityFailure as exc:
            return {
                "status": "fail",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "http_status": exc.http_status,
                "retryable": is_retryable_failure(
                    status_code=exc.http_status,
                    response_text=exc.response_text,
                ),
                "error": redact_text(
                    exc.response_text or str(exc),
                    [self.config.api_key],
                ),
            }
        except Exception as exc:  # defensive reporting for the diagnostic CLI
            return {
                "status": "fail",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "http_status": None,
                "retryable": is_retryable_failure(exception=exc),
                "error": redact_text(
                    f"{type(exc).__name__}: {exc}",
                    [self.config.api_key],
                ),
            }
        return {
            "status": "pass",
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "http_status": 200,
            "retryable": False,
            "evidence": evidence,
        }


def load_provider_configs() -> dict[str, ProviderConfig]:
    settings = get_settings()
    return {
        "huomiao": ProviderConfig(
            name="huomiao",
            base_url=settings.text_fallback_openai_base_url,
            api_key=settings.text_fallback_api_key.strip(),
            model=settings.text_fallback_model.strip(),
        ),
        "lio": ProviderConfig(
            name="lio",
            base_url=settings.lio_openai_base_url,
            api_key=settings.lio_api_key.strip(),
            model=settings.lio_model.strip(),
        ),
    }


def probe_provider(
    config: ProviderConfig,
    *,
    capabilities: list[str],
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
            "configuration": "invalid",
            "configuration_error": f"Missing required fields: {', '.join(missing)}",
            "capabilities": {
                capability: {
                    "status": "fail",
                    "latency_ms": 0,
                    "http_status": None,
                    "retryable": False,
                    "error": "Provider configuration is incomplete",
                }
                for capability in capabilities
            },
        }

    probe = ProviderProbe(config, timeout_seconds=timeout_seconds)
    return {
        "provider": config.name,
        "host": config.host,
        "model": config.model,
        "configuration": "valid",
        "capabilities": {
            capability: probe.run_capability(capability) for capability in capabilities
        },
    }


def parse_capabilities(raw: str) -> list[str]:
    capabilities = [part.strip() for part in raw.split(",") if part.strip()]
    unknown = sorted(set(capabilities) - set(CAPABILITY_NAMES))
    if unknown:
        raise argparse.ArgumentTypeError(
            f"Unknown capabilities: {', '.join(unknown)}; "
            f"choose from {', '.join(CAPABILITY_NAMES)}"
        )
    if not capabilities:
        raise argparse.ArgumentTypeError("At least one capability is required")
    return capabilities


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=("all", "huomiao", "lio"),
        default="all",
        help="Provider to probe independently (default: all)",
    )
    parser.add_argument(
        "--capabilities",
        type=parse_capabilities,
        default=list(CAPABILITY_NAMES),
        help=f"Comma-separated subset of: {', '.join(CAPABILITY_NAMES)}",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=90.0,
        help="Per-request timeout; the probe performs no retry (default: 90)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report path",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be greater than zero")

    configs = load_provider_configs()
    provider_names = list(configs) if args.provider == "all" else [args.provider]
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probe_policy": {
            "retry_attempts": 0,
            "cross_provider_fallback": False,
            "timeout_seconds_per_request": args.timeout_seconds,
        },
        "providers": [
            probe_provider(
                configs[provider_name],
                capabilities=args.capabilities,
                timeout_seconds=args.timeout_seconds,
            )
            for provider_name in provider_names
        ],
    }

    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    any_failure = any(
        capability["status"] != "pass"
        for provider in report["providers"]
        for capability in provider["capabilities"].values()
    )
    return 1 if any_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
