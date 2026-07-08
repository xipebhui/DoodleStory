import logging
from datetime import datetime
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import GenerationTask
from app.models.enums import TaskStatus

logger = logging.getLogger(__name__)
MAX_ALERT_FIELD_CHARS = 400


def truncate_alert_field(value: object, *, max_chars: int = MAX_ALERT_FIELD_CHARS) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."


def task_failure_alert_url(task: GenerationTask) -> str | None:
    settings = get_settings()
    base_url = settings.task_failure_alert_task_base_url.strip().rstrip("/")
    if not base_url:
        base_url = next((origin for origin in settings.frontend_origin_list if origin.startswith(("http://", "https://"))), "")
    if not base_url:
        return None
    return f"{base_url}/tasks/{task.id}"


def enum_value(value: Any) -> str:
    return getattr(value, "value", str(value or ""))


def build_task_failure_alert_text(task: GenerationTask) -> str:
    lines = [
        "DoodleStory 图文任务失败告警",
        f"任务 ID：{task.id}",
        f"标题：{truncate_alert_field(task.display_title, max_chars=120)}",
        f"用户 ID：{task.owner_user_id}",
        f"输入模式：{enum_value(task.story_input_mode)}",
        f"当前步骤：{enum_value(task.current_step) or '-'}",
        f"生图模型：{truncate_alert_field(task.image_model_name_snapshot, max_chars=120)}",
        f"风格：{truncate_alert_field(task.style_name_snapshot, max_chars=120)}",
        f"错误码：{truncate_alert_field(task.error_code, max_chars=120) or '-'}",
        f"错误信息：{truncate_alert_field(task.error_message) or '-'}",
        f"失败时间：{(task.finished_at or datetime.utcnow()).isoformat(timespec='seconds')}",
    ]
    url = task_failure_alert_url(task)
    if url:
        lines.append(f"任务链接：{url}")
    return "\n".join(lines)


def send_feishu_text_webhook(webhook_url: str, text: str, timeout_seconds: int) -> None:
    response = requests.post(
        webhook_url,
        json={"msg_type": "text", "content": {"text": text}},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("飞书 webhook 返回内容不是 JSON 对象")
    code = body.get("code", body.get("StatusCode"))
    if code not in (None, 0, "0"):
        message = body.get("msg", body.get("StatusMessage", body))
        raise RuntimeError(f"飞书 webhook 返回失败：{message}")


def notify_generation_task_failure_if_needed(db: Session, task: GenerationTask) -> bool:
    settings = get_settings()
    webhook_url = settings.task_failure_alert_webhook_url.strip()
    if not webhook_url:
        return False
    if task.status != TaskStatus.failed or task.failure_alert_sent_at is not None:
        return False

    try:
        send_feishu_text_webhook(
            webhook_url,
            build_task_failure_alert_text(task),
            settings.task_failure_alert_timeout_seconds,
        )
    except Exception as exc:
        logger.warning(
            "failed to send generation task failure alert task_id=%s error_type=%s error=%s",
            task.id,
            exc.__class__.__name__,
            exc,
        )
        db.rollback()
        return False

    task.failure_alert_sent_at = datetime.utcnow()
    db.commit()
    logger.info("sent generation task failure alert task_id=%s", task.id)
    return True
