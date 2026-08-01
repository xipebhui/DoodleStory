import asyncio
from pathlib import Path
import unittest
from unittest.mock import patch

from app.core.runtime_instance_lock import RuntimeInstanceLock, runtime_lock_path
from app.main import create_app, settings


class RuntimeInstanceLockTest(unittest.TestCase):
    def test_same_database_cannot_hold_two_runtime_locks(self) -> None:
        first = RuntimeInstanceLock.for_database("sqlite:////tmp/doodlestory-lock-a.db")
        second = RuntimeInstanceLock.for_database("sqlite:////tmp/doodlestory-lock-a.db")

        first.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, "already owns startup recovery"):
                second.acquire()
        finally:
            first.release()

    def test_runtime_lock_can_be_reacquired_after_release(self) -> None:
        first = RuntimeInstanceLock.for_database("sqlite:////tmp/doodlestory-lock-b.db")
        second = RuntimeInstanceLock.for_database("sqlite:////tmp/doodlestory-lock-b.db")

        first.acquire()
        first.release()
        second.acquire()
        second.release()

    def test_different_databases_use_different_runtime_locks(self) -> None:
        first = RuntimeInstanceLock.for_database("sqlite:////tmp/doodlestory-lock-c.db")
        second = RuntimeInstanceLock.for_database("sqlite:////tmp/doodlestory-lock-d.db")

        first.acquire()
        second.acquire()
        second.release()
        first.release()

    def test_runtime_lock_file_contains_owner_pid(self) -> None:
        database_url = "sqlite:////tmp/doodlestory-lock-owner.db"
        instance_lock = RuntimeInstanceLock.for_database(database_url)

        instance_lock.acquire()
        try:
            lock_contents = Path(runtime_lock_path(database_url)).read_text(encoding="utf-8")
        finally:
            instance_lock.release()

        self.assertTrue(lock_contents.startswith("pid="))

    def test_startup_failure_releases_runtime_lock(self) -> None:
        app = create_app()

        with patch(
            "app.main.initialize_runtime_skill_registry",
            side_effect=RuntimeError("startup failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "startup failed"):
                asyncio.run(app.router.on_startup[0]())

        replacement = RuntimeInstanceLock.for_database(settings.resolved_database_url)
        replacement.acquire()
        replacement.release()
