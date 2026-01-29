from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable

from kmi_manager_cli.config import Config
from kmi_manager_cli.locking import file_lock


MSK_OFFSET = timedelta(hours=3)


def msk_now_str() -> str:
    return (datetime.now(timezone.utc) + MSK_OFFSET).strftime("%Y-%m-%d %H:%M:%S MSK")


def trace_path(config: Config) -> Path:
    path = config.state_dir.expanduser() / "trace" / "trace.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_trace(config: Config, entry: dict) -> None:
    path = trace_path(config)
    with file_lock(path):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def load_trace_entries(path: Path, window: int = 200) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    tail = lines[-window:]
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
