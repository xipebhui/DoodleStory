from __future__ import annotations

from contextlib import contextmanager
import hashlib
import logging
import os
import re
import subprocess
from typing import Any, Iterator

from app.core.config import PROJECT_ROOT, Settings, get_settings


logger = logging.getLogger(__name__)
REDACTED = "[REDACTED]"
CONTENT_OMITTED = {"content_recorded": False}
SENSITIVE_KEY_MARKERS = (
    "access_token",
    "api_key",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "headers",
    "password",
    "path",
    "refresh_token",
    "secret",
    "url",
)
CONTENT_KEY_MARKERS = (
    "content",
    "input",
    "instructions",
    "kwargs",
    "message",
    "output",
    "prompt",
    "request",
    "response",
)
URL_PATTERN = re.compile(r"(?i)\b(?:https?|file)://[^\s\"'<>]+")
ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![\w.-])/(?:Users|home|opt|tmp|var)/[^\s\"'<>]+")
AUTHORIZATION_PATTERN = re.compile(
    r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;\"'}]+"
)
BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")

_initialized = False
_enabled = False
_trace_content = False
_experiment_name = ""
_configured_secrets: tuple[str, ...] = ()


class AgentObservabilityConfigurationError(RuntimeError):
    pass


def _mlflow():
    import mlflow

    return mlflow


def _safe_text(value: str) -> str:
    redacted = value
    for secret in _configured_secrets:
        if secret:
            redacted = redacted.replace(secret, REDACTED)
    redacted = AUTHORIZATION_PATTERN.sub(r"\1[REDACTED]", redacted)
    redacted = BEARER_PATTERN.sub(r"\1[REDACTED]", redacted)
    redacted = URL_PATTERN.sub(REDACTED, redacted)
    redacted = ABSOLUTE_PATH_PATTERN.sub(REDACTED, redacted)
    return redacted


def sanitize_trace_value(
    value: Any,
    *,
    allow_content: bool,
    field_name: str = "",
) -> Any:
    lowered = field_name.lower()
    if lowered.endswith("_request_id") and isinstance(value, str):
        return _safe_text(value)
    if (lowered.endswith("_tokens") or lowered == "requests") and isinstance(
        value, (int, float)
    ):
        return value
    if any(marker in lowered for marker in SENSITIVE_KEY_MARKERS):
        return REDACTED
    if not allow_content and any(marker in lowered for marker in CONTENT_KEY_MARKERS):
        return REDACTED
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, dict):
        return {
            str(key): sanitize_trace_value(
                item,
                allow_content=allow_content,
                field_name=str(key),
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            sanitize_trace_value(item, allow_content=allow_content, field_name=field_name)
            for item in value
        ]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _safe_text(str(value))


def _trace_span_processor(span) -> None:
    if not _trace_content:
        span.set_inputs(CONTENT_OMITTED)
        span.set_outputs(CONTENT_OMITTED)
    else:
        span.set_inputs(sanitize_trace_value(span.inputs, allow_content=True))
        span.set_outputs(sanitize_trace_value(span.outputs, allow_content=True))

    for key, value in span.attributes.items():
        safe_value = sanitize_trace_value(
            value,
            allow_content=_trace_content,
            field_name=key,
        )
        if safe_value != value:
            span.set_attribute(key, safe_value)


def _runtime_git_commit() -> str | None:
    for name in ("GIT_COMMIT", "SOURCE_COMMIT", "COOLIFY_GIT_COMMIT_SHA"):
        value = os.getenv(name, "").strip()
        if value:
            return value[:40]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value[:40] if value else None


def initialize_agent_observability(settings: Settings | None = None) -> None:
    global _configured_secrets, _enabled, _experiment_name, _initialized, _trace_content

    selected = settings or get_settings()
    if not selected.mlflow_tracing_enabled:
        _initialized = True
        _enabled = False
        return
    tracking_uri = selected.mlflow_tracking_uri.strip()
    experiment_name = selected.mlflow_experiment_name.strip()
    missing = []
    if not tracking_uri:
        missing.append("MLFLOW_TRACKING_URI")
    if not experiment_name:
        missing.append("MLFLOW_EXPERIMENT_NAME")
    if missing:
        raise AgentObservabilityConfigurationError(
            f"MLflow tracing 已启用但缺少配置: {', '.join(missing)}"
        )
    if (
        selected.app_env != "test"
        and not tracking_uri.startswith(("http://", "https://"))
    ):
        raise AgentObservabilityConfigurationError(
            "MLFLOW_TRACKING_URI 必须使用 HTTP(S) Tracking Server，"
            "禁止直接使用本地文件或数据库 URI，以免 MLflow 系统标签暴露内部路径"
        )

    try:
        # Keep trace export synchronous so a runtime backend outage is surfaced to
        # agent_span and logged with agent_run_id instead of failing later in an
        # uncorrelated background exporter.
        os.environ["MLFLOW_ENABLE_ASYNC_TRACE_LOGGING"] = "false"
        mlflow = _mlflow()
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        _trace_content = selected.mlflow_trace_content
        _configured_secrets = tuple(
            value
            for value in (
                selected.text_fallback_api_key,
                selected.lio_api_key,
                selected.image_gateway_api_key,
            )
            if value
        )
        mlflow.tracing.configure(span_processors=[_trace_span_processor])
        mlflow.openai.autolog(
            disable=False,
            silent=False,
            log_traces=True,
            disable_openai_agent_tracer=True,
        )
    except Exception as exc:
        reason = _safe_text(f"{type(exc).__name__}: {exc}")
        raise AgentObservabilityConfigurationError(
            f"MLflow tracing 初始化失败: {reason}"
        ) from exc

    _experiment_name = experiment_name
    _initialized = True
    _enabled = True


def reset_agent_observability_for_tests() -> None:
    global _configured_secrets, _enabled, _experiment_name, _initialized, _trace_content
    _configured_secrets = ()
    _enabled = False
    _experiment_name = ""
    _initialized = False
    _trace_content = False
    os.environ.pop("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", None)


def is_agent_observability_enabled() -> bool:
    return _enabled


def safe_idempotency_digest(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def record_observability_error(agent_run_id: str | None, exc: Exception) -> None:
    logger.error(
        "observability_error agent_run_id=%s error_type=%s reason=%s",
        agent_run_id,
        type(exc).__name__,
        _safe_text(str(exc)),
    )


def _set_span_attributes(span, attributes: dict[str, Any]) -> None:
    if span is None:
        return
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(
                key,
                sanitize_trace_value(value, allow_content=_trace_content, field_name=key),
            )


@contextmanager
def agent_span(
    name: str,
    *,
    agent_run_id: str | None,
    span_type: str,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any | None]:
    if not _enabled:
        yield None
        return

    mlflow = _mlflow()
    manager = None
    span = None
    body_error: BaseException | None = None
    try:
        manager = mlflow.start_span(
            name=name,
            span_type=span_type,
            attributes=attributes or {},
        )
        span = manager.__enter__()
    except Exception as exc:
        record_observability_error(agent_run_id, exc)
        yield None
        return

    try:
        yield span
    except BaseException as exc:
        body_error = exc
        raise
    finally:
        try:
            if manager is not None:
                if body_error is None:
                    manager.__exit__(None, None, None)
                else:
                    manager.__exit__(
                        type(body_error),
                        body_error,
                        body_error.__traceback__,
                    )
        except Exception as exc:
            record_observability_error(agent_run_id, exc)


@contextmanager
def agent_run_span(
    *,
    agent_run_id: str,
    conversation_id: str,
    turn_id: str,
    task_id: str | None,
    model: str,
    app_environment: str,
) -> Iterator[Any | None]:
    attributes = {
        "agent_run_id": agent_run_id,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "task_id": task_id,
        "agent_model": model,
        "app_environment": app_environment,
        "git_commit": _runtime_git_commit(),
    }
    with agent_span(
        "agent.run",
        agent_run_id=agent_run_id,
        span_type="AGENT",
        attributes=attributes,
    ) as span:
        if span is not None:
            try:
                _mlflow().update_current_trace(
                    tags={key: str(value) for key, value in attributes.items() if value is not None}
                )
            except Exception as exc:
                record_observability_error(agent_run_id, exc)
        yield span


def set_agent_run_trace_status(
    span,
    *,
    agent_run_id: str,
    run_status: str,
    task_id: str | None,
    error_code: str | None,
) -> None:
    try:
        _set_span_attributes(
            span,
            {
                "run_status": run_status,
                "task_id": task_id,
                "error_code": error_code,
            },
        )
        if span is not None:
            span.set_status("ERROR" if run_status == "failed" else "OK")
        if _enabled and span is not None:
            tags = {"agent_run_id": agent_run_id, "run_status": run_status}
            if task_id:
                tags["task_id"] = task_id
            _mlflow().update_current_trace(
                tags=tags,
                state="ERROR" if run_status == "failed" else "OK",
            )
    except Exception as exc:
        record_observability_error(agent_run_id, exc)


def set_span_result(span, attributes: dict[str, Any]) -> None:
    try:
        _set_span_attributes(span, attributes)
    except Exception as exc:
        record_observability_error(None, exc)


def set_span_status(span, status: str, *, agent_run_id: str | None = None) -> None:
    if span is None:
        return
    try:
        span.set_status(status)
    except Exception as exc:
        record_observability_error(agent_run_id, exc)


def current_trace_id() -> str | None:
    if not _enabled:
        return None
    try:
        span = _mlflow().get_current_active_span()
        return span.trace_id if span is not None else None
    except Exception as exc:
        record_observability_error(None, exc)
        return None


def experiment_name() -> str:
    return _experiment_name
