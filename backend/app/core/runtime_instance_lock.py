from __future__ import annotations

import fcntl
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


def runtime_lock_path(database_url: str) -> Path:
    database_key = hashlib.sha256(database_url.encode("utf-8")).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / f"doodlestory-runtime-{database_key}.lock"


@dataclass
class RuntimeInstanceLock:
    path: Path
    _file_descriptor: int | None = None

    @classmethod
    def for_database(cls, database_url: str) -> RuntimeInstanceLock:
        return cls(path=runtime_lock_path(database_url))

    def acquire(self) -> None:
        if self._file_descriptor is not None:
            raise RuntimeError(f"DoodleStory runtime lock is already held: {self.path}")

        file_descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(file_descriptor)
            raise RuntimeError(
                "Another DoodleStory backend already owns startup recovery for "
                f"this database (lock: {self.path})"
            ) from exc

        os.ftruncate(file_descriptor, 0)
        os.write(file_descriptor, f"pid={os.getpid()}\n".encode("utf-8"))
        os.fsync(file_descriptor)
        self._file_descriptor = file_descriptor

    def release(self) -> None:
        file_descriptor = self._file_descriptor
        if file_descriptor is None:
            return
        self._file_descriptor = None
        try:
            fcntl.flock(file_descriptor, fcntl.LOCK_UN)
        finally:
            os.close(file_descriptor)
