from __future__ import annotations

from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from kmi_manager_cli.config import Config
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.proxy import create_app, parse_listen
from kmi_manager_cli.state import State


def test_parse_listen() -> None:
    host, port = parse_listen("127.0.0.1:54123")
    assert host == "127.0.0.1"
    assert port == 54123


def test_proxy_dry_run_response(tmp_path: Path) -> None:
    config = Config(
        auths_dir=tmp_path,
        proxy_listen="127.0.0.1:54123",
        proxy_base_path="/kmi-rotor/v1",
        upstream_base_url="https://example.com/api",
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
    registry = Registry(keys=[KeyRecord(label="alpha", api_key="sk-test-a")], active_index=0)
    state = State()
    app = create_app(config, registry, state)
    client = TestClient(app)

    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["upstream_url"].endswith("/models")


def test_proxy_upstream_error_returns_502(tmp_path: Path, monkeypatch) -> None:
    class FailingClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def stream(self, *args, **kwargs):
            raise httpx.ConnectError("boom", request=None)

        async def aclose(self) -> None:
            return None

    def _client_factory(*args, **kwargs):
        return FailingClient()

    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", _client_factory)

    config = Config(
        auths_dir=tmp_path,
        proxy_listen="127.0.0.1:54123",
        proxy_base_path="/kmi-rotor/v1",
        upstream_base_url="https://example.com/api",
        state_dir=tmp_path,
        dry_run=False,
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
    registry = Registry(keys=[KeyRecord(label="alpha", api_key="sk-test-a")], active_index=0)
    state = State()
    app = create_app(config, registry, state)
    client = TestClient(app)

    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 502
    assert resp.json()["error"] == "Upstream request failed"


def test_proxy_per_key_rate_limit(tmp_path: Path) -> None:
    config = Config(
        auths_dir=tmp_path,
        proxy_listen="127.0.0.1:54123",
        proxy_base_path="/kmi-rotor/v1",
        upstream_base_url="https://example.com/api",
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
        proxy_max_rps_per_key=0,
        proxy_max_rpm_per_key=1,
    )
    registry = Registry(keys=[KeyRecord(label="alpha", api_key="sk-test-a")], active_index=0)
    state = State()
    app = create_app(config, registry, state)
    client = TestClient(app)

    assert client.get("/kmi-rotor/v1/models").status_code == 200
    second = client.get("/kmi-rotor/v1/models")
    assert second.status_code == 429
    assert "rate limit" in second.json()["error"].lower()


def test_proxy_global_rate_limit(tmp_path: Path) -> None:
    config = Config(
        auths_dir=tmp_path,
        proxy_listen="127.0.0.1:54123",
        proxy_base_path="/kmi-rotor/v1",
        upstream_base_url="https://example.com/api",
        state_dir=tmp_path,
        dry_run=True,
        auto_rotate_allowed=True,
        rotation_cooldown_seconds=300,
        proxy_allow_remote=False,
        proxy_token="",
        proxy_max_rps=0,
        proxy_max_rpm=1,
        proxy_retry_max=0,
        proxy_retry_base_ms=250,
        env_path=None,
        proxy_max_rps_per_key=0,
        proxy_max_rpm_per_key=0,
    )
    registry = Registry(keys=[KeyRecord(label="alpha", api_key="sk-test-a")], active_index=0)
    state = State()
    app = create_app(config, registry, state)
    client = TestClient(app)

    assert client.get("/kmi-rotor/v1/models").status_code == 200
    second = client.get("/kmi-rotor/v1/models")
    assert second.status_code == 429
    assert "rate limit" in second.json()["error"].lower()
