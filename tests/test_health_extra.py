from __future__ import annotations

from types import SimpleNamespace

import httpx

from kmi_manager_cli import health as health_module


def test_window_hours_variants() -> None:
    assert health_module._window_hours({"duration": 30, "timeUnit": "MINUTE"}) == 0.5
    assert health_module._window_hours({"duration": 2, "timeUnit": "DAY"}) == 48.0
    assert health_module._window_hours({"duration": 1, "timeUnit": "WEEK"}) == 168.0
    assert health_module._window_hours({"duration": 1, "timeUnit": "UNKNOWN"}) is None


def test_limit_label_prefers_name_and_title() -> None:
    label = health_module._limit_label({"name": "primary"}, {}, {}, 0)
    assert label == "primary"
    label = health_module._limit_label({}, {"title": "secondary"}, {}, 0)
    assert label == "secondary"


def test_extract_reset_hint_variants() -> None:
    assert health_module._extract_reset_hint({"reset_at": "2024-01-01"}) == "2024-01-01"
    assert health_module._extract_reset_hint({"reset_in": 120}) == "resets in 120s"


def test_extract_remaining_percent_invalid_values() -> None:
    assert health_module._extract_remaining_percent({"remaining_percent": "bad"}) is None
    assert health_module._extract_remaining_percent({"remaining": "x", "total": 5}) is None
    assert (
        health_module._extract_remaining_percent({"data": {"remaining": "x", "total": "y"}})
        is None
    )


def test_extract_email_from_payload_data() -> None:
    payload = {"data": {"email": "data@example.com"}}
    assert health_module._extract_email_from_payload(payload) == "data@example.com"


def test_window_hours_invalid_duration() -> None:
    assert health_module._window_hours({"duration": "bad", "timeUnit": "HOUR"}) is None


def test_extract_usage_summary_uses_limits() -> None:
    payload = {
        "limits": [
            {"detail": {"used": 10, "limit": 100, "remaining": 90, "reset_in": 60}}
        ]
    }
    used, limit, remaining, reset_hint = health_module._extract_usage_summary(payload)
    assert used == 10
    assert limit == 100
    assert remaining == 90
    assert reset_hint == "resets in 60s"


def test_extract_usage_summary_from_usage() -> None:
    payload = {"usage": {"used": 1, "limit": 2, "remaining": 1, "reset_time": "soon"}}
    used, limit, remaining, reset_hint = health_module._extract_usage_summary(payload)
    assert used == 1
    assert limit == 2
    assert remaining == 1
    assert reset_hint == "soon"


def test_parse_limits_skips_non_dict() -> None:
    payload = {"limits": ["bad", {"detail": {"used": 1, "limit": 2, "remaining": 1}}]}
    limits = health_module._parse_limits(payload)
    assert len(limits) == 1


def test_fetch_usage_adjusts_remaining_percent(monkeypatch) -> None:
    payload = {"remaining_percent": 10, "usage": {"used": 50, "limit": 100}}

    class DummyResponse:
        def __init__(self) -> None:
            self.content = b"{}"

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    monkeypatch.setattr(httpx, "get", lambda *a, **k: DummyResponse())

    usage = health_module.fetch_usage(
        "https://example.com",
        "sk-test",
        dry_run=False,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
    )
    assert usage is not None
    assert usage.remaining_percent == 50.0


def test_fetch_usage_uses_limits_when_percent_missing(monkeypatch) -> None:
    payload = {
        "limits": [
            {
                "detail": {"used": 20, "limit": 100, "remaining": 80},
                "window": {"duration": 1, "timeUnit": "DAY"},
            }
        ]
    }

    class DummyResponse:
        def __init__(self) -> None:
            self.content = b"{}"

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    monkeypatch.setattr(httpx, "get", lambda *a, **k: DummyResponse())

    usage = health_module.fetch_usage(
        "https://example.com",
        "sk-test",
        dry_run=False,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
    )
    assert usage is not None
    assert usage.remaining_percent == 80.0


def test_fetch_usage_logs_on_error(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("boom", request=None)

    calls = {}

    def fake_log_event(_logger, message, **fields):
        calls["message"] = message
        calls["fields"] = fields

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(health_module, "log_event", fake_log_event)

    usage = health_module.fetch_usage(
        "https://example.com",
        "sk-test",
        dry_run=False,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        label="alpha",
    )
    assert usage is None
    assert calls["message"] == "usage_fetch_failed"
    assert calls["fields"]["key_label"] == "alpha"


def test_fetch_usage_error_without_logger(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("boom", request=None)

    monkeypatch.setattr(httpx, "get", fake_get)
    usage = health_module.fetch_usage(
        "https://example.com",
        "sk-test",
        dry_run=False,
        logger=None,
    )
    assert usage is None


def test_get_accounts_health_force_real(monkeypatch, tmp_path) -> None:
    config = health_module.Config(
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
    account = health_module.Account(
        id="acc",
        label="alpha",
        api_key="sk-test",
        base_url="https://example.com",
        source="alpha.env",
    )
    state = health_module.State()
    calls = {}

    def fake_fetch_usage(base_url, api_key, dry_run, logger=None, label=None):
        calls["dry_run"] = dry_run
        return health_module.Usage(
            remaining_percent=100.0,
            used=0,
            limit=100,
            remaining=100,
            reset_hint=None,
            limits=[],
            raw={},
        )

    monkeypatch.setattr(health_module, "fetch_usage", fake_fetch_usage)
    health = health_module.get_accounts_health(config, [account], state, force_real=True)
    assert calls["dry_run"] is False
    assert health["acc"].status == "healthy"


def test_looks_like_email_rejects_invalid() -> None:
    assert health_module._looks_like_email(123) is None
    assert health_module._looks_like_email("no-at-symbol") is None
    assert health_module._looks_like_email("user@local") is None


def test_extract_email_from_payload_top_level_and_account() -> None:
    payload = {"email": "top@example.com"}
    assert health_module._extract_email_from_payload(payload) == "top@example.com"

    payload = {"account": {"user_email": "acct@example.com"}}
    assert health_module._extract_email_from_payload(payload) == "acct@example.com"


def test_limit_label_fractional_hours() -> None:
    label = health_module._limit_label({}, {}, {"duration": 90, "timeUnit": "MINUTE"}, 0)
    assert label == "1.5h limit"


def test_extract_usage_summary_with_non_dict_limits() -> None:
    used, limit, remaining, reset_hint = health_module._extract_usage_summary(
        {"limits": ["bad"]}
    )
    assert used is None
    assert limit is None
    assert remaining is None
    assert reset_hint is None


def test_fetch_usage_uses_best_limit_candidate(monkeypatch) -> None:
    payload = {
        "limits": [
            {"detail": {"used": "bad", "limit": "bad", "remaining": "bad"}},
            {
                "detail": {"used": 10, "limit": 100, "remaining": 90},
                "window": {"duration": 2, "timeUnit": "DAY"},
            },
        ]
    }

    class DummyResponse:
        def __init__(self) -> None:
            self.content = b"{}"

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    monkeypatch.setattr(httpx, "get", lambda *a, **k: DummyResponse())

    usage = health_module.fetch_usage(
        "https://example.com",
        "sk-test",
        dry_run=False,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
    )
    assert usage is not None
    assert usage.remaining_percent == 90.0


def test_score_key_blocks_when_remaining_zero() -> None:
    usage = health_module.Usage(
        remaining_percent=0.0,
        used=100,
        limit=100,
        remaining=0,
        reset_hint=None,
        limits=[],
        raw={},
    )
    key_state = health_module.KeyState()
    assert health_module.score_key(usage, key_state, exhausted=False, blocked=False) == "blocked"
