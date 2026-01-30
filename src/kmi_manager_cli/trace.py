from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from kmi_manager_cli.config import Config
from kmi_manager_cli.locking import file_lock
from kmi_manager_cli.logging import get_logger
from kmi_manager_cli.security import warn_if_insecure
from kmi_manager_cli.time_utils import format_timestamp, resolve_timezone


TRACE_SCHEMA_VERSION = 1
_CHECKED_PATHS: set[Path] = set()


def trace_now_str(config: Config) -> str:
    tzinfo = resolve_timezone(config.time_zone)
    return format_timestamp(datetime.now(timezone.utc), tzinfo)


def trace_path(config: Config) -> Path:
    path = config.state_dir.expanduser() / "trace" / "trace.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _rotate_trace(path: Path, max_backups: int) -> None:
    if max_backups <= 0:
        if path.exists():
            path.unlink()
        return
    for idx in range(max_backups, 0, -1):
        src = path.with_suffix(path.suffix + f".{idx}")
        dst = path.with_suffix(path.suffix + f".{idx + 1}")
        if src.exists():
            src.replace(dst)
    if path.exists():
        path.replace(path.with_suffix(path.suffix + ".1"))


def _rotate_trace_if_needed(path: Path, max_bytes: int, max_backups: int) -> None:
    if max_bytes <= 0:
        return
    if path.exists() and path.stat().st_size >= max_bytes:
        _rotate_trace(path, max_backups)


def append_trace(config: Config, entry: dict) -> None:
    entry.setdefault("schema_version", TRACE_SCHEMA_VERSION)
    path = trace_path(config)
    if path not in _CHECKED_PATHS:
        logger = get_logger(config)
        warn_if_insecure(path.parent, logger, "trace_dir")
        if path.exists():
            warn_if_insecure(path, logger, "trace_file")
        _CHECKED_PATHS.add(path)
    with file_lock(path):
        _rotate_trace_if_needed(path, config.trace_max_bytes, config.trace_max_backups)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _tail_lines(path: Path, limit: int) -> list[str]:
    if limit <= 0:
        return []
    buffer = deque()
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        chunk = b""
        while position > 0 and len(buffer) <= limit:
            read_size = min(4096, position)
            position -= read_size
            handle.seek(position, os.SEEK_SET)
            data = handle.read(read_size)
            chunk = data + chunk
            lines = chunk.splitlines()
            if len(lines) > limit:
                buffer = deque(lines[-limit:])
                break
            buffer = deque(lines)
        return [line.decode("utf-8", errors="ignore") for line in buffer]


def load_trace_entries(path: Path, window: int = 200) -> list[dict]:
    if not path.exists():
        return []
    with file_lock(path):
        tail = _tail_lines(path, window)
    entries: list[dict] = []
    for line in tail:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def compute_confidence(entries: Iterable[dict]) -> float:
    entries = list(entries)
    if not entries:
        return 100.0
    counts: dict[str, int] = {}
    for entry in entries:
        label = entry.get("key_label", "unknown")
        counts[label] = counts.get(label, 0) + 1
    total = len(entries)
    num_keys = max(len(counts), 1)
    expected = total / num_keys
    if expected == 0:
        return 100.0
    max_dev = max(abs(count - expected) / expected for count in counts.values())
    confidence = max(0.0, 100.0 - (max_dev * 100))
    return round(confidence, 2)


def compute_distribution(entries: Iterable[dict]) -> tuple[dict[str, int], int]:
    counts: dict[str, int] = {}
    total = 0
    for entry in entries:
        label = entry.get("key_label", "unknown")
        counts[label] = counts.get(label, 0) + 1
        total += 1
    return counts, total
