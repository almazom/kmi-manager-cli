from __future__ import annotations

from pathlib import Path

from kmi_manager_cli.config import Config
from kmi_manager_cli.trace import append_trace, compute_confidence, load_trace_entries, trace_path


def test_compute_confidence_balanced() -> None:
    entries = [
        {"key_label": "a"},
        {"key_label": "b"},
        {"key_label": "a"},
        {"key_label": "b"},
    ]
    assert compute_confidence(entries) == 100.0


def test_compute_confidence_skewed() -> None:
    entries = [
        {"key_label": "a"},
        {"key_label": "a"},
        {"key_label": "a"},
        {"key_label": "b"},
    ]
    assert compute_confidence(entries) < 100.0


def test_append_and_load_trace(tmp_path: Path) -> None:
    config = Config(
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
    )
    append_trace(config, {"key_label": "a", "status": 200})
    entries = load_trace_entries(trace_path(config), window=10)
    assert entries[-1]["key_label"] == "a"
