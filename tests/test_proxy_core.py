from __future__ import annotations

import asyncio
from types import SimpleNamespace

from starlette.requests import Request

from kmi_manager_cli import proxy as proxy_module
from kmi_manager_cli.config import Config
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import State


def _make_config(tmp_path) -> Config:
    return Config(
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
        enforce_file_perms=False,
    )


def _make_request(headers: dict[str, str]) -> Request:
    raw_headers = [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
        "scheme": "http",
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 1234),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_parse_listen_invalid() -> None:
    try:
        proxy_module.parse_listen("missing_port")
    except ValueError as exc:
        assert "host:port" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_build_upstream_url_with_query(tmp_path) -> None:
    config = _make_config(tmp_path)
    url = proxy_module._build_upstream_url(config, "models", "a=1")
    assert url == "https://example.com/api/models?a=1"


def test_is_local_host() -> None:
    assert proxy_module._is_local_host("127.0.0.1") is True
    assert proxy_module._is_local_host("localhost") is True
    assert proxy_module._is_local_host("::1") is True
    assert proxy_module._is_local_host("10.0.0.1") is False


def test_authorize_request_headers() -> None:
    assert proxy_module._authorize_request(_make_request({}), token="") is True
    assert proxy_module._authorize_request(
        _make_request({"authorization": "Bearer secret"}), token="secret"
    ) is True
    assert proxy_module._authorize_request(
        _make_request({"x-kmi-proxy-token": "token"}), token="token"
    ) is True
    assert proxy_module._authorize_request(
        _make_request({"authorization": "Bearer wrong"}), token="secret"
    ) is False


def test_rate_limiter_rps(monkeypatch) -> None:
    limiter = proxy_module.RateLimiter(max_rps=2, max_rpm=0)
    monkeypatch.setattr(proxy_module.time, "time", lambda: 1000.0)

    async def run():
        assert await limiter.allow() is True
        assert await limiter.allow() is True
        assert await limiter.allow() is False

    asyncio.run(run())


def test_rate_limiter_rpm(monkeypatch) -> None:
    limiter = proxy_module.RateLimiter(max_rps=0, max_rpm=2)
    monkeypatch.setattr(proxy_module.time, "time", lambda: 1000.0)

    async def run():
        assert await limiter.allow() is True
        assert await limiter.allow() is True
        assert await limiter.allow() is False

    asyncio.run(run())


def test_keyed_rate_limiter(monkeypatch) -> None:
    limiter = proxy_module.KeyedRateLimiter(max_rps=0, max_rpm=1)
    monkeypatch.setattr(proxy_module.time, "time", lambda: 1000.0)

    async def run():
        assert await limiter.allow("a") is True
        assert await limiter.allow("b") is True
        assert await limiter.allow("a") is False

    asyncio.run(run())


def test_select_key_uses_active_key(tmp_path) -> None:
    config = _make_config(tmp_path)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")], active_index=0)
    state = State(active_index=0)
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=registry,
        state=state,
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(),
        trace_writer=SimpleNamespace(),
    )
    selected = proxy_module._select_key(ctx)
    assert selected == ("a", "sk-a")


def test_state_writer_mark_dirty_without_task(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    state = State()
    lock = asyncio.Lock()
    writer = proxy_module.StateWriter(config=config, state=state, lock=lock)
    calls = {"saved": 0}

    def fake_save_state(_config, _state):
        calls["saved"] += 1

    monkeypatch.setattr(proxy_module, "save_state", fake_save_state)

    async def run():
        await writer.mark_dirty()

    asyncio.run(run())
    assert calls["saved"] == 1


def test_trace_writer_enqueue_without_task(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    logger = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
    writer = proxy_module.TraceWriter(config=config, logger=logger)
    calls = {"count": 0}

    def fake_append_trace(_config, _entry):
        calls["count"] += 1

    monkeypatch.setattr(proxy_module, "append_trace", fake_append_trace)
    writer.enqueue({"ok": True})
    assert calls["count"] == 1
