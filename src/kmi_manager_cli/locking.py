from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - platform-specific
    fcntl = None


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    lock_path = _lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        if fcntl:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        else:
            fd = None
            while fd is None:
                try:
                    fd = os.open(str(lock_path) + ".win", os.O_CREAT | os.O_EXCL | os.O_RDWR)
                except FileExistsError:
                    time.sleep(0.05)
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:
                if fd is not None:
                    os.close(fd)
                    try:
                        os.unlink(str(lock_path) + ".win")
                    except FileNotFoundError:
                        pass


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)
