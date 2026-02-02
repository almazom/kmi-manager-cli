from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from kmi_manager_cli import proxy as proxy_module
from kmi_manager_cli.config import Config
from kmi_manager_cli.health import Usage
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import KeyState, State


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
        usage_cache_seconds=1,
        blocklist_recheck_seconds=1,
        blocklist_recheck_max=1,
    )


def test_coerce_prompt_text_variants() -> None:
    assert proxy_module._coerce_prompt_text("hello") == "hello"
    assert proxy_module._coerce_prompt_text({"text": "alpha"}) == "alpha"
    assert proxy_module._coerce_prompt_text({"content": "bravo"}) == "bravo"
    assert proxy_module._coerce_prompt_text([{"content": "charlie"}]) == "charlie"
    assert proxy_module._coerce_prompt_text(123) == ""


def test_extract_prompt_meta_non_json() -> None:
    head, hint = proxy_module._extract_prompt_meta(b"plain", "text/plain")
    assert head == ""
    assert hint == ""


def test_extract_prompt_meta_prompt_field() -> None:
    payload = {"prompt": "hello world again"}
    body = json.dumps(payload).encode("utf-8")
    head, hint = proxy_module._extract_prompt_meta(body, "application/json")
    assert head.startswith("hello")
    assert hint == "hello"


def test_parse_retry_after_http_date() -> None:
    retry = proxy_module._parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT")
    assert retry == 0


def test_collect_error_strings_nested() -> None:
    payload = {"error": {"message": "bad"}, "details": {"error_code": "E1"}}
    bucket: list[str] = []
    proxy_module._collect_error_strings(payload, bucket)
    assert "bad" in bucket


def test_extract_error_hint_text() -> None:
    hint = proxy_module._extract_error_hint(b"plain error", "text/plain")
    assert hint == "plain error"


def test_build_upstream_url_empty_path(tmp_path) -> None:
    config = _make_config(tmp_path)
    assert proxy_module._build_upstream_url(config, "", "") == "https://example.com/api"


def test_run_proxy_rejects_remote_bind(tmp_path) -> None:
    config = _make_config(tmp_path)
    config = Config(**{**config.__dict__, "proxy_listen": "10.0.0.1:9999"})
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State()
    try:
        proxy_module.run_proxy(config, registry, state)
    except ValueError as exc:
        assert "Remote proxy binding is disabled" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_run_proxy_requires_tls_and_token(tmp_path) -> None:
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State()

    config_tls = _make_config(tmp_path)
    config_tls = Config(
        **{
            **config_tls.__dict__,
            "proxy_listen": "10.0.0.1:9999",
            "proxy_allow_remote": True,
            "proxy_require_tls": True,
            "proxy_tls_terminated": False,
        }
    )
    try:
        proxy_module.run_proxy(config_tls, registry, state)
    except ValueError as exc:
        assert "TLS termination" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

    config_token = Config(
        **{
            **config_tls.__dict__,
            "proxy_tls_terminated": True,
            "proxy_token": "",
        }
    )
    try:
        proxy_module.run_proxy(config_token, registry, state)
    except ValueError as exc:
        assert "KMI_PROXY_TOKEN" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_maybe_refresh_health_updates_cache(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State()
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=registry,
        state=state,
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
    )

    monkeypatch.setattr(proxy_module, "get_health_map", lambda *_args, **_kwargs: {"a": "ok"})
    monkeypatch.setattr(proxy_module.time, "time", lambda: 1000.0)

    async def run():
        await proxy_module._maybe_refresh_health(ctx)

    asyncio.run(run())
    assert ctx.health_cache == {"a": "ok"}
    assert ctx.health_cache_ts == 1000.0


def test_maybe_recheck_blocked_clears(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State(keys={"a": KeyState(blocked_reason="payment")})
    ctx = proxy_module.ProxyContext(
        config=config,
        registry=registry,
        state=state,
        rate_limiter=proxy_module.RateLimiter(0, 0),
        key_rate_limiter=proxy_module.KeyedRateLimiter(0, 0),
        state_lock=asyncio.Lock(),
        state_writer=SimpleNamespace(mark_dirty=lambda: asyncio.sleep(0)),
        trace_writer=SimpleNamespace(),
    )

    monkeypatch.setattr(proxy_module.time, "time", lambda: 1000.0)
    monkeypatch.setattr(
        proxy_module,
        "fetch_usage",
        lambda *_args, **_kwargs: Usage(
            remaining_percent=100.0,
            used=0,
            limit=100,
            remaining=100,
            reset_hint=None,
            limits=[],
            raw={},
        ),
    )

    async def run():
        await proxy_module._maybe_recheck_blocked(ctx)

    asyncio.run(run())
    assert state.keys["a"].blocked_reason is None


def test_state_writer_flushes_task(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    state = State()
    calls = {"saved": 0}

    def fake_save_state(_config, _state):
        calls["saved"] += 1

    monkeypatch.setattr(proxy_module, "save_state", fake_save_state)

    async def run():
        lock = asyncio.Lock()
        writer = proxy_module.StateWriter(config=config, state=state, lock=lock, debounce_seconds=0)
        await writer.start()
        await writer.mark_dirty()
        await asyncio.sleep(0)
        await writer.stop()

    asyncio.run(run())
    assert calls["saved"] >= 1


def test_trace_writer_run_consumes_queue(monkeypatch, tmp_path) -> None:
    config = _make_config(tmp_path)
    calls = {"count": 0}

    def fake_append_trace(_config, _entry):
        calls["count"] += 1

    monkeypatch.setattr(proxy_module, "append_trace", fake_append_trace)

    async def run():
        logger = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
        writer = proxy_module.TraceWriter(config=config, logger=logger)
        await writer.start()
        writer.enqueue({"ok": True})
        await asyncio.sleep(0.05)
        await writer.stop()

    asyncio.run(run())
    assert calls["count"] >= 1
