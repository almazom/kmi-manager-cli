from __future__ import annotations

import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from kmi_manager_cli.config import Config
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.proxy import create_app
from kmi_manager_cli.state import KeyState, State


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        headers: dict[str, str] | None = None,
        content: bytes = b"",
        is_stream_consumed: bool = True,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._content = content
        self.is_stream_consumed = is_stream_consumed

    @property
    def content(self) -> bytes:
        return self._content

    async def aread(self) -> bytes:
        return self._content

    def aiter_raw(self):
        async def gen():
            yield self._content

        return gen()


class FakeStream:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return None


class FakeAsyncClient:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = 0

    def stream(self, *args, **kwargs):
        item = self.sequence[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return FakeStream(item)

    async def aclose(self) -> None:
        return None


def _make_config(tmp_path, **overrides) -> Config:
    base = Config(
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
        proxy_retry_base_ms=1,
        env_path=None,
        enforce_file_perms=False,
    )
    return Config(**{**base.__dict__, **overrides})


def test_proxy_unauthorized_when_token_required(tmp_path) -> None:
    config = _make_config(tmp_path, proxy_token="secret", dry_run=True)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State()
    client = TestClient(create_app(config, registry, state))

    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 401


def test_proxy_no_keys_returns_503(tmp_path) -> None:
    config = _make_config(tmp_path, dry_run=True)
    registry = Registry(keys=[])
    state = State()
    client = TestClient(create_app(config, registry, state))

    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 503


def test_proxy_rate_limit_exceeded(tmp_path) -> None:
    config = _make_config(tmp_path, dry_run=True, proxy_max_rpm=1)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State()
    client = TestClient(create_app(config, registry, state))

    assert client.get("/kmi-rotor/v1/models").status_code == 200
    assert client.get("/kmi-rotor/v1/models").status_code == 429


def test_proxy_retries_on_stream_error(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, proxy_retry_max=1)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State(keys={"a": KeyState()})
    client = TestClient(create_app(config, registry, state))

    sequence = [
        httpx.ConnectError("boom", request=None),
        FakeResponse(200, content=b"ok"),
    ]
    fake_client = FakeAsyncClient(sequence)
    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", lambda *a, **k: fake_client)
    orig_sleep = asyncio.sleep
    monkeypatch.setattr("kmi_manager_cli.proxy.asyncio.sleep", lambda *_a, **_k: orig_sleep(0))

    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 200
    assert fake_client.calls == 2


def test_proxy_retries_on_429(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, proxy_retry_max=1)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State()
    client = TestClient(create_app(config, registry, state))

    sequence = [
        FakeResponse(429, headers={"retry-after": "1"}, content=b""),
        FakeResponse(200, content=b"ok"),
    ]
    fake_client = FakeAsyncClient(sequence)
    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", lambda *a, **k: fake_client)
    orig_sleep = asyncio.sleep
    monkeypatch.setattr("kmi_manager_cli.proxy.asyncio.sleep", lambda *_a, **_k: orig_sleep(0))

    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 200
    assert fake_client.calls == 2


def test_proxy_payment_required_marks_blocked(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State(keys={"a": KeyState()})
    client = TestClient(create_app(config, registry, state))

    payload = json.dumps({"error": "payment required"}).encode("utf-8")
    sequence = [
        FakeResponse(
            403,
            headers={"content-type": "application/json"},
            content=payload,
            is_stream_consumed=True,
        )
    ]
    fake_client = FakeAsyncClient(sequence)
    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", lambda *a, **k: fake_client)

    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 403
    assert state.keys["a"].blocked_reason == "payment_required"


def test_proxy_streaming_response(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State()
    client = TestClient(create_app(config, registry, state))

    sequence = [
        FakeResponse(200, content=b"stream", is_stream_consumed=False),
    ]
    fake_client = FakeAsyncClient(sequence)
    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", lambda *a, **k: fake_client)

    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 200
    assert resp.content == b"stream"
