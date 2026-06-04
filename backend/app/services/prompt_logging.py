import json
import logging
from typing import Any

from pydantic import BaseModel

from app.core.config import get_settings


def _max_chars() -> int:
    return max(1000, get_settings().prompt_trace_log_max_chars)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _trim_text(value: str) -> str:
    max_chars = _max_chars()
    if len(value) <= max_chars:
        return value
    marker = f"...[truncated total_chars={len(value)} max_chars={max_chars}]"
    return value[:max_chars] + marker


def _normalize(value: Any) -> Any:
    jsonable = _jsonable(value)
    if isinstance(jsonable, str):
        return _trim_text(jsonable)
    if isinstance(jsonable, dict):
        return {key: _normalize(item) for key, item in jsonable.items()}
    if isinstance(jsonable, list):
        return [_normalize(item) for item in jsonable]
    return jsonable


def log_prompt_trace(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        **{key: _normalize(value) for key, value in fields.items()},
    }
    logger.info("prompt_trace %s", json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))
