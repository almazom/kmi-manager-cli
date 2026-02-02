from __future__ import annotations

import json
from pathlib import Path

from kmi_manager_cli import trace as trace_module
from kmi_manager_cli.config import Config


def _make_config(tmp_path: Path) -> Config:
    return Config(
        auths_dir=tmp_path,
        proxy_listen="127.0.0.1:54123",
        proxy_base_path="/kmi-rotor/v1",
        upstream_base_url="https://example.com",
        state_dir=tmp_path,
        dry_run=True,
        auto_rotate_allowed=True,
        rotation_cooldown_seconds=300,
        proxy_allow_remote=False,
        proxy_token="",
        proxy_max_rps=0,
        proxy_max_rpm=0,
        proxy_retry_max=0,
        proxy_retry_base_ms=250,
        env_path=None,
        enforce_file_perms=False,
    )


def test_rotate_trace_removes_when_backups_zero(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("data\n", encoding="utf-8")
    trace_module._rotate_trace(path, max_backups=0)
    assert not path.exists()


def test_rotate_trace_noop_when_missing_and_backups_zero(tmp_path: Path) -> None:
    path = tmp_path / "missing.jsonl"
    trace_module._rotate_trace(path, max_backups=0)
    assert not path.exists()


def test_rotate_trace_shifts_backups(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("current\n", encoding="utf-8")
    (tmp_path / "trace.jsonl.1").write_text("old1\n", encoding="utf-8")
    (tmp_path / "trace.jsonl.2").write_text("old2\n", encoding="utf-8")

    trace_module._rotate_trace(path, max_backups=2)

    assert not path.exists()
    assert (tmp_path / "trace.jsonl.1").read_text(encoding="utf-8") == "current\n"
    assert (tmp_path / "trace.jsonl.2").read_text(encoding="utf-8") == "old1\n"
    assert (tmp_path / "trace.jsonl.3").read_text(encoding="utf-8") == "old2\n"


def test_rotate_trace_if_needed(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("x" * 10, encoding="utf-8")
    trace_module._rotate_trace_if_needed(path, max_bytes=5, max_backups=1)
    assert (tmp_path / "trace.jsonl.1").exists()


def test_rotate_trace_if_needed_noop_when_disabled(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("x" * 10, encoding="utf-8")
    trace_module._rotate_trace_if_needed(path, max_bytes=0, max_backups=1)
    assert path.exists()


def test_tail_lines_returns_last_lines(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("a\nb\nc\nd\n", encoding="utf-8")
    tail = trace_module._tail_lines(path, limit=2)
    assert [line.strip() for line in tail] == ["c", "d"]


def test_tail_lines_limit_zero(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("a\nb\n", encoding="utf-8")
    assert trace_module._tail_lines(path, limit=0) == []


def test_load_trace_entries_skips_invalid(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("not-json\n" + json.dumps({"ok": True}) + "\n", encoding="utf-8")
    entries = trace_module.load_trace_entries(path, window=10)
    assert entries == [{"ok": True}]


def test_load_trace_entries_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.jsonl"
    assert trace_module.load_trace_entries(path, window=10) == []


def test_trace_path_creates_dir(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    path = trace_module.trace_path(config)
    assert path.parent.exists()


def test_compute_confidence_empty() -> None:
    assert trace_module.compute_confidence([]) == 100.0


def test_compute_distribution_counts() -> None:
    entries = [{"key_label": "a"}, {"key_label": "b"}, {"key_label": "a"}]
    counts, total = trace_module.compute_distribution(entries)
    assert total == 3
    assert counts["a"] == 2
    assert counts["b"] == 1
