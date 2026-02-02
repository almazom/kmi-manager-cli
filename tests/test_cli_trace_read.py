from __future__ import annotations

import json
from pathlib import Path

from kmi_manager_cli.cli import _read_new_trace_entries


def test_read_new_trace_entries_handles_partial_line(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    first = json.dumps({"a": 1}) + "\n"
    second = json.dumps({"b": 2})
    path.write_text(first + second, encoding="utf-8")

    entries, offset = _read_new_trace_entries(path, 0)
    assert entries == [{"a": 1}]
    assert offset == len(first)

    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")

    entries, offset = _read_new_trace_entries(path, offset)
    assert entries == [{"b": 2}]
    assert offset == path.stat().st_size


def test_read_new_trace_entries_resets_on_truncate(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    first = json.dumps({"a": "longer"}) + "\n"
    path.write_text(first, encoding="utf-8")

    entries, offset = _read_new_trace_entries(path, 0)
    assert entries == [{"a": "longer"}]

    path.write_text(json.dumps({"c": 3}) + "\n", encoding="utf-8")

    entries, offset = _read_new_trace_entries(path, offset)
    assert entries == [{"c": 3}]
    assert offset == path.stat().st_size
