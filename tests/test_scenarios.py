from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from kmi_manager_cli.config import Config
from kmi_manager_cli.health import HealthInfo
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.proxy import create_app
from kmi_manager_cli.rotation import rotate_manual
from kmi_manager_cli.state import KeyState, State
from kmi_manager_cli.trace import load_trace_entries, trace_path


def test_rotate_manual_raises_when_no_eligible_keys() -> None:
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a"), KeyRecord(label="b", api_key="sk-b")])
    state = State(keys={"a": KeyState(error_401=1), "b": KeyState(error_401=1)})
    health = {
        "a": HealthInfo(
            status="blocked",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=1.0,
        ),
        "b": HealthInfo(
            status="blocked",
            remaining_percent=None,
            used=None,
            limit=None,
            remaining=None,
            reset_hint=None,
            limits=[],
            error_rate=1.0,
        ),
    }
    with pytest.raises(RuntimeError):
        rotate_manual(registry, state, health=health)


def test_proxy_marks_exhausted_on_429(tmp_path: Path, monkeypatch) -> None:
    class RateLimitedClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        class _Stream:
            async def __aenter__(self):
                request = httpx.Request("GET", "https://example.com")
                return httpx.Response(429, request=request, content=b"{}")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        def stream(self, *args, **kwargs):
            return self._Stream()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", lambda *args, **kwargs: RateLimitedClient())

    config = Config(
        auths_dir=tmp_path,
        proxy_listen="127.0.0.1:54123",
        proxy_base_path="/kmi-rotor/v1",
        upstream_base_url="https://example.com/api",
        state_dir=tmp_path,
        dry_run=False,
        auto_rotate_allowed=True,
        rotation_cooldown_seconds=60,
        proxy_allow_remote=False,
        proxy_token="",
        proxy_max_rps=0,
        proxy_max_rpm=0,
        proxy_retry_max=0,
        proxy_retry_base_ms=250,
        env_path=None,
    )
    registry = Registry(keys=[KeyRecord(label="alpha", api_key="sk-test-a")], active_index=0)
    state = State(keys={"alpha": KeyState()})
    app = create_app(config, registry, state)
    client = TestClient(app)

    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 429
    assert state.keys["alpha"].error_429 == 1
    assert state.keys["alpha"].exhausted_until is not None


def test_load_trace_entries_skips_corrupt_lines(tmp_path: Path) -> None:
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
    path = trace_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bad json}\n{\"key_label\": \"ok\"}\n", encoding="utf-8")

    entries = load_trace_entries(path, window=10)
    assert len(entries) == 1
    assert entries[0]["key_label"] == "ok"
