from __future__ import annotations

import asyncio
import json
from collections import deque
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from kmi_manager_cli import proxy as proxy_module
from kmi_manager_cli.config import Config
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import KeyState, State


def _make_config(tmp_path, **overrides) -> Config:
    base = Config(
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
        proxy_retry_base_ms=1,
        env_path=None,
        enforce_file_perms=False,
        usage_cache_seconds=1,
        blocklist_recheck_seconds=1,
        blocklist_recheck_max=1,
    )
    return Config(**{**base.__dict__, **overrides})


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
    def __init__(self, response) -> None:
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


def test_filter_hop_by_hop_headers_ignores_empty_tokens() -> None:
    headers = [("Connection", " , keep-alive, "), ("X-Test", "1")]
    filtered = proxy_module._filter_hop_by_hop_headers(headers)
    assert "x-test" in {k.lower() for k in filtered}


def test_coerce_prompt_text_empty_branches() -> None:
    assert proxy_module._coerce_prompt_text({"content": {"nope": True}}) == ""
    assert proxy_module._coerce_prompt_text([{"content": {"text": ""}}]) == ""


def test_trim_prompt_empty_and_max_chars() -> None:
    assert proxy_module._trim_prompt("") == ""
    assert proxy_module._trim_prompt("   ") == ""
    trimmed = proxy_module._trim_prompt("a" * 100, max_words=10, max_chars=10)
    assert trimmed.endswith("...")


def test_first_word_empty() -> None:
    assert proxy_module._first_word("") == ""
    assert proxy_module._first_word("   ") == ""


def test_extract_prompt_meta_invalid_json() -> None:
    head, hint = proxy_module._extract_prompt_meta(b"{", "application/json")
    assert head == ""
    assert hint == ""


def test_extract_prompt_meta_falls_back_to_prompt() -> None:
    payload = {"messages": ["bad"], "prompt": "hello world again"}
    body = json.dumps(payload).encode("utf-8")
    head, hint = proxy_module._extract_prompt_meta(body, "application/json")
    assert head.startswith("hello")
    assert hint == "hello"


def test_extract_prompt_meta_non_dict_payload() -> None:
    body = json.dumps(["not-a-dict"]).encode("utf-8")
    head, hint = proxy_module._extract_prompt_meta(body, "application/json")
    assert head == ""
    assert hint == ""


def test_parse_retry_after_strips_whitespace() -> None:
    assert proxy_module._parse_retry_after("   ") is None


def test_parse_retry_after_naive_http_date() -> None:
    retry = proxy_module._parse_retry_after("Wed, 21 Oct 2015 07:28:00")
    assert retry == 0


def test_collect_error_strings_list_and_error_prefix() -> None:
    bucket: list[str] = []
    payload = [{"errorMessage": "boom"}, 123]
    proxy_module._collect_error_strings(payload, bucket)
    assert "boom" in bucket
    assert "123" in bucket


def test_extract_error_hint_empty_and_invalid_json() -> None:
    assert proxy_module._extract_error_hint(b"", "application/json") == ""
    assert proxy_module._extract_error_hint(b"   ", "text/plain") == ""
    assert proxy_module._extract_error_hint(b"{", "application/json") == "{"


def test_close_stream_handles_none() -> None:
    class DummyClient:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    class DummyStream:
        def __init__(self) -> None:
            self.closed = False

        async def __aexit__(self, exc_type, exc, tb) -> None:
            self.closed = True

    async def run():
        stream = DummyStream()
        client = DummyClient()
        await proxy_module._close_stream(stream, client)
        assert stream.closed is True
        # Client is now shared and managed by lifespan, not closed per-request
        assert client.closed is False

        client2 = DummyClient()
        await proxy_module._close_stream(None, client2)
        assert client2.closed is False

    asyncio.run(run())


def test_maybe_refresh_health_skips_when_interval_zero(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, usage_cache_seconds=0)
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=Registry(keys=[]),
        state=State(),
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
    )

    monkeypatch.setattr(proxy_module, "get_health_map", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("called")))

    async def run():
        await proxy_module._maybe_refresh_health(ctx)

    asyncio.run(run())


def test_maybe_refresh_health_skips_when_cache_fresh(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, usage_cache_seconds=10)
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=Registry(keys=[]),
        state=State(),
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
        health_cache_ts=1000.0,
    )

    monkeypatch.setattr(proxy_module.time, "time", lambda: 1005.0)
    monkeypatch.setattr(proxy_module, "get_health_map", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("called")))

    async def run():
        await proxy_module._maybe_refresh_health(ctx)

    asyncio.run(run())


def test_maybe_recheck_blocked_skips_interval_zero(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, blocklist_recheck_seconds=0)
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=Registry(keys=[KeyRecord(label="a", api_key="sk-a")]),
        state=State(keys={"a": KeyState(blocked_reason="payment")}),
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
    )

    monkeypatch.setattr(proxy_module, "fetch_usage", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("called")))

    async def run():
        await proxy_module._maybe_recheck_blocked(ctx)

    asyncio.run(run())


def test_maybe_recheck_blocked_skips_recent(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, blocklist_recheck_seconds=10)
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=Registry(keys=[KeyRecord(label="a", api_key="sk-a")]),
        state=State(keys={"a": KeyState(blocked_reason="payment")}),
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
        blocklist_recheck_ts=1000.0,
    )

    monkeypatch.setattr(proxy_module.time, "time", lambda: 1005.0)
    monkeypatch.setattr(proxy_module, "fetch_usage", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("called")))

    async def run():
        await proxy_module._maybe_recheck_blocked(ctx)

    asyncio.run(run())


def test_maybe_recheck_blocked_no_candidates(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, blocklist_recheck_seconds=1)
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=Registry(keys=[KeyRecord(label="a", api_key="sk-a")]),
        state=State(keys={"a": KeyState()}),
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
    )

    monkeypatch.setattr(proxy_module.time, "time", lambda: 1000.0)
    monkeypatch.setattr(proxy_module, "fetch_usage", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("called")))

    async def run():
        await proxy_module._maybe_recheck_blocked(ctx)

    asyncio.run(run())


def test_maybe_recheck_blocked_no_clear_when_usage_none(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, blocklist_recheck_seconds=1)
    state = State(keys={"a": KeyState(blocked_reason="payment")})
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=Registry(keys=[KeyRecord(label="a", api_key="sk-a")]),
        state=state,
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
    )

    monkeypatch.setattr(proxy_module.time, "time", lambda: 1000.0)
    monkeypatch.setattr(proxy_module, "fetch_usage", lambda *_a, **_k: None)

    async def run():
        await proxy_module._maybe_recheck_blocked(ctx)

    asyncio.run(run())
    assert state.keys["a"].blocked_reason == "payment"


def test_health_refresh_loop_timeout_continue(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=Registry(keys=[]),
        state=State(),
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
    )

    async def fake_wait_for(_awaitable, timeout):
        _awaitable.close()
        ctx.health_stop.set()
        raise asyncio.TimeoutError

    monkeypatch.setattr(proxy_module.asyncio, "wait_for", fake_wait_for)

    async def run():
        await proxy_module._health_refresh_loop(ctx)

    asyncio.run(run())


def test_state_writer_start_idempotent(tmp_path) -> None:
    config = _make_config(tmp_path)
    state = State()

    async def run():
        writer = proxy_module.StateWriter(config=config, state=state, lock=asyncio.Lock())
        await writer.start()
        task = writer._task
        await writer.start()
        assert writer._task is task
        await writer.stop()

    asyncio.run(run())


def test_state_writer_stop_without_task(tmp_path) -> None:
    config = _make_config(tmp_path)
    state = State()

    async def run():
        writer = proxy_module.StateWriter(config=config, state=state, lock=asyncio.Lock())
        await writer.stop()

    asyncio.run(run())


def test_state_writer_run_skips_save_when_not_dirty(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    state = State()
    calls = {"saved": 0}

    def fake_save_state(_config, _state):
        calls["saved"] += 1

    monkeypatch.setattr(proxy_module, "save_state", fake_save_state)

    async def run():
        writer = proxy_module.StateWriter(config=config, state=state, lock=asyncio.Lock(), debounce_seconds=0)
        writer._stop.set()
        writer._flush.set()
        await writer._run()

    asyncio.run(run())
    assert calls["saved"] == 0


def test_trace_writer_start_idempotent(tmp_path) -> None:
    config = _make_config(tmp_path)

    async def run():
        writer = proxy_module.TraceWriter(config=config, logger=SimpleNamespace())
        await writer.start()
        task = writer._task
        await writer.start()
        assert writer._task is task
        await writer.stop()

    asyncio.run(run())


def test_trace_writer_enqueue_queue_full(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    calls = {}

    def fake_log_event(_logger, message, **fields):
        calls["message"] = message
        calls["fields"] = fields

    writer = proxy_module.TraceWriter(config=config, logger=SimpleNamespace())
    writer.queue = asyncio.Queue(maxsize=1)
    writer._task = object()

    writer.queue.put_nowait({"ok": True})

    monkeypatch.setattr(proxy_module, "log_event", fake_log_event)
    writer.enqueue({"ok": False})

    assert writer.dropped == 1
    assert calls["message"] == "trace_queue_full"


def test_trace_writer_stop_without_task(tmp_path) -> None:
    config = _make_config(tmp_path)

    async def run():
        writer = proxy_module.TraceWriter(config=config, logger=SimpleNamespace())
        await writer.stop()

    asyncio.run(run())


def test_trace_writer_run_timeout_continue(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)

    async def fake_wait_for(_awaitable, timeout):
        fake_wait_for.calls += 1
        _awaitable.close()
        if fake_wait_for.calls == 2:
            writer._stop.set()
        raise asyncio.TimeoutError

    fake_wait_for.calls = 0

    async def run():
        nonlocal writer
        writer = proxy_module.TraceWriter(config=config, logger=SimpleNamespace())
        monkeypatch.setattr(proxy_module.asyncio, "wait_for", fake_wait_for)
        await writer._run()

    writer = None
    asyncio.run(run())


def test_rate_limiter_prunes_old_and_breaks(monkeypatch) -> None:
    limiter = proxy_module.RateLimiter(max_rps=1, max_rpm=0)
    now = 1000.0
    limiter.recent.extend([now - 120, now - 2])
    monkeypatch.setattr(proxy_module.time, "time", lambda: now)

    async def run():
        assert await limiter.allow() is True

    asyncio.run(run())


def test_keyed_rate_limiter_prunes_old_and_breaks(monkeypatch) -> None:
    limiter = proxy_module.KeyedRateLimiter(max_rps=1, max_rpm=0)
    now = 1000.0
    limiter.recent["a"] = deque([now - 120, now - 2])
    monkeypatch.setattr(proxy_module.time, "time", lambda: now)

    async def run():
        assert await limiter.allow("a") is True

    asyncio.run(run())


def test_select_key_returns_none_when_no_keys(tmp_path) -> None:
    config = _make_config(tmp_path)
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=Registry(keys=[]),
        state=State(),
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
    )
    assert proxy_module._select_key(ctx) is None


def test_app_lifespan_runs(tmp_path) -> None:
    config = _make_config(tmp_path, usage_cache_seconds=0, blocklist_recheck_seconds=0)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State()
    app = proxy_module.create_app(config, registry, state)
    with TestClient(app) as client:
        resp = client.get("/kmi-rotor/v1/models")
        assert resp.status_code == 200


def test_proxy_stream_error_after_context(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, dry_run=False, proxy_retry_max=0)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State(keys={"a": KeyState()})

    stream_closed = {"flag": False}
    client_closed = {"flag": False}

    class ErrorStream:
        async def __aenter__(self):
            raise httpx.ConnectError("boom", request=None)

        async def __aexit__(self, exc_type, exc, tb):
            stream_closed["flag"] = True

    class ErrorClient:
        def stream(self, *args, **kwargs):
            return ErrorStream()

        async def aclose(self) -> None:
            client_closed["flag"] = True

    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", lambda *a, **k: ErrorClient())

    client = TestClient(proxy_module.create_app(config, registry, state))
    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 502
    assert stream_closed["flag"] is True
    # Client is now shared and managed by lifespan, not closed per-request
    assert client_closed["flag"] is False


def test_proxy_retries_on_500(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, dry_run=False, proxy_retry_max=1)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State(keys={"a": KeyState()})

    sequence = [
        FakeResponse(500, content=b"fail"),
        FakeResponse(200, content=b"ok"),
    ]
    fake_client = FakeAsyncClient(sequence)
    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", lambda *a, **k: fake_client)
    orig_sleep = asyncio.sleep
    monkeypatch.setattr(proxy_module.asyncio, "sleep", lambda *_a, **_k: orig_sleep(0))

    client = TestClient(proxy_module.create_app(config, registry, state))
    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 200
    assert fake_client.calls == 2


def test_proxy_consumed_response_closes_stream(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, dry_run=False)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State(keys={"a": KeyState()})

    sequence = [FakeResponse(200, content=b"ok", is_stream_consumed=True)]
    fake_client = FakeAsyncClient(sequence)
    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", lambda *a, **k: fake_client)

    closed = {"flag": False}

    async def fake_close_stream(_stream, _client):
        closed["flag"] = True

    monkeypatch.setattr(proxy_module, "_close_stream", fake_close_stream)

    client = TestClient(proxy_module.create_app(config, registry, state))
    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 200
    assert closed["flag"] is True


def test_proxy_marks_exhausted_on_500(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, dry_run=False)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State(keys={"a": KeyState()})

    sequence = [FakeResponse(500, content=b"error")]
    fake_client = FakeAsyncClient(sequence)
    monkeypatch.setattr("kmi_manager_cli.proxy.httpx.AsyncClient", lambda *a, **k: fake_client)

    client = TestClient(proxy_module.create_app(config, registry, state))
    resp = client.get("/kmi-rotor/v1/models")
    assert resp.status_code == 500
    assert state.keys["a"].exhausted_until is not None


def test_run_proxy_invokes_uvicorn(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path, proxy_listen="127.0.0.1:9999")
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State()
    calls = {}

    import uvicorn

    def fake_run(app, host, port, lifespan):
        calls["host"] = host
        calls["port"] = port
        calls["lifespan"] = lifespan

    monkeypatch.setattr(uvicorn, "run", fake_run)

    proxy_module.run_proxy(config, registry, state)
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 9999
    assert calls["lifespan"] == "on"
