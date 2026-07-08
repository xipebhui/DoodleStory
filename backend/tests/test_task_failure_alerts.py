import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.models.enums import GenerationStepName, ImageCountMode, StoryInputMode, TaskStatus
from app.services.task_failure_alerts import build_task_failure_alert_text, notify_generation_task_failure_if_needed


class FakeDb:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


class FakeResponse:
    def __init__(self, body: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.body = body or {"code": 0, "msg": "success"}
        self.error = error

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error

    def json(self) -> dict[str, object]:
        return self.body


def failed_task(**overrides: object) -> SimpleNamespace:
    values = {
        "id": "task-1",
        "owner_user_id": "user-1",
        "display_title": "失败任务",
        "original_text": "这段用户原文不应该出现在告警里",
        "story_input_mode": StoryInputMode.knowledge_plan,
        "image_count_mode": ImageCountMode.auto,
        "current_step": GenerationStepName.generate_images,
        "image_model_name_snapshot": "gpt-image-2",
        "style_name_snapshot": "知识图鉴风",
        "status": TaskStatus.failed,
        "error_code": "ImageGenerationFailed",
        "error_message": "所有分镜图片生成失败",
        "finished_at": datetime(2026, 7, 8, 12, 0, 0),
        "failure_alert_sent_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def alert_settings(**overrides: object) -> SimpleNamespace:
    values = {
        "task_failure_alert_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/test",
        "task_failure_alert_timeout_seconds": 10,
        "task_failure_alert_task_base_url": "http://8.141.96.236",
        "frontend_origin_list": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TaskFailureAlertsTest(unittest.TestCase):
    def test_notify_failure_sends_feishu_text_once_and_marks_sent(self) -> None:
        task = failed_task()
        db = FakeDb()

        with patch("app.services.task_failure_alerts.get_settings", return_value=alert_settings()), patch(
            "app.services.task_failure_alerts.requests.post",
            return_value=FakeResponse(),
        ) as post:
            sent = notify_generation_task_failure_if_needed(db, task)  # type: ignore[arg-type]

        self.assertTrue(sent)
        self.assertIsNotNone(task.failure_alert_sent_at)
        self.assertEqual(1, db.commit_count)
        self.assertEqual(0, db.rollback_count)
        post.assert_called_once()
        payload = post.call_args.kwargs["json"]
        self.assertEqual("text", payload["msg_type"])
        text = payload["content"]["text"]
        self.assertIn("DoodleStory 图文任务失败告警", text)
        self.assertIn("任务链接：http://8.141.96.236/tasks/task-1", text)
        self.assertNotIn("用户原文", text)

    def test_notify_failure_skips_when_alert_already_sent(self) -> None:
        task = failed_task(failure_alert_sent_at=datetime(2026, 7, 8, 12, 1, 0))
        db = FakeDb()

        with patch("app.services.task_failure_alerts.get_settings", return_value=alert_settings()), patch(
            "app.services.task_failure_alerts.requests.post"
        ) as post:
            sent = notify_generation_task_failure_if_needed(db, task)  # type: ignore[arg-type]

        self.assertFalse(sent)
        post.assert_not_called()
        self.assertEqual(0, db.commit_count)

    def test_notify_failure_logs_and_keeps_unsent_when_webhook_fails(self) -> None:
        task = failed_task()
        db = FakeDb()

        with patch("app.services.task_failure_alerts.get_settings", return_value=alert_settings()), patch(
            "app.services.task_failure_alerts.requests.post",
            return_value=FakeResponse(error=RuntimeError("network failed")),
        ):
            sent = notify_generation_task_failure_if_needed(db, task)  # type: ignore[arg-type]

        self.assertFalse(sent)
        self.assertIsNone(task.failure_alert_sent_at)
        self.assertEqual(0, db.commit_count)
        self.assertEqual(1, db.rollback_count)

    def test_alert_text_omits_task_link_when_no_base_url_is_configured(self) -> None:
        task = failed_task()

        with patch(
            "app.services.task_failure_alerts.get_settings",
            return_value=alert_settings(task_failure_alert_task_base_url="", frontend_origin_list=[]),
        ):
            text = build_task_failure_alert_text(task)  # type: ignore[arg-type]

        self.assertNotIn("任务链接：", text)


if __name__ == "__main__":
    unittest.main()
