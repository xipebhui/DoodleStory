from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Iterator


_GROKCLI_EXECUTION_LOCK = Lock()


@contextmanager
def serialized_grokcli_call() -> Iterator[None]:
    """Serialize grokcli credential access inside the single app process.

    grokcli uses POSIX ``fcntl`` for its own cross-process credential lock and
    that lock is a no-op on Windows. DoodleStory enforces one backend process
    per database, so this shared lock protects concurrent image/video calls in
    the supported Windows development runtime.
    """

    with _GROKCLI_EXECUTION_LOCK:
        yield
