from __future__ import annotations

import errno
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


_WINDOWS_LOCK_BYTE_OFFSET = 4096


def runtime_lock_path(database_url: str) -> Path:
    database_key = hashlib.sha256(database_url.encode("utf-8")).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / f"doodlestory-runtime-{database_key}.lock"


def _acquire_file_lock(file_descriptor: int) -> None:
    if os.name == "nt":
        os.lseek(file_descriptor, _WINDOWS_LOCK_BYTE_OFFSET, os.SEEK_SET)
        try:
            msvcrt.locking(file_descriptor, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise BlockingIOError from exc
            raise
        return

    fcntl.flock(file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_file_lock(file_descriptor: int) -> None:
    if os.name == "nt":
        os.lseek(file_descriptor, _WINDOWS_LOCK_BYTE_OFFSET, os.SEEK_SET)
        msvcrt.locking(file_descriptor, msvcrt.LK_UNLCK, 1)
        return

    fcntl.flock(file_descriptor, fcntl.LOCK_UN)


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
            _acquire_file_lock(file_descriptor)
        except BlockingIOError as exc:
            os.close(file_descriptor)
            raise RuntimeError(
                "Another DoodleStory backend already owns startup recovery for "
                f"this database (lock: {self.path})"
            ) from exc
        except BaseException:
            os.close(file_descriptor)
            raise

        owner_metadata = f"pid={os.getpid()}\n".encode("utf-8")
        try:
            os.lseek(file_descriptor, 0, os.SEEK_SET)
            os.write(file_descriptor, owner_metadata)
            os.ftruncate(file_descriptor, len(owner_metadata))
            os.fsync(file_descriptor)
        except BaseException:
            try:
                _release_file_lock(file_descriptor)
            finally:
                os.close(file_descriptor)
            raise
        self._file_descriptor = file_descriptor

    def release(self) -> None:
        file_descriptor = self._file_descriptor
        if file_descriptor is None:
            return
        self._file_descriptor = None
        try:
            _release_file_lock(file_descriptor)
        finally:
            os.close(file_descriptor)
