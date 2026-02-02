from __future__ import annotations

import json
import logging

from kmi_manager_cli import audit, errors, logging as logging_module


def test_current_actor_prefers_kmi_audit_actor(monkeypatch) -> None:
    monkeypatch.setenv("KMI_AUDIT_ACTOR", "ci-user")
    monkeypatch.setenv("USER", "fallback")
    assert audit.current_actor() == "ci-user"


def test_current_actor_falls_back_to_user(monkeypatch) -> None:
    monkeypatch.delenv("KMI_AUDIT_ACTOR", raising=False)
    monkeypatch.setenv("USER", "alice")
    assert audit.current_actor() == "alice"


def test_current_actor_unknown_when_no_env(monkeypatch) -> None:
    monkeypatch.delenv("KMI_AUDIT_ACTOR", raising=False)
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    assert audit.current_actor() == "unknown"


def test_log_audit_event_uses_log_event(monkeypatch) -> None:
    calls = {}

    def fake_log_event(logger, message, **fields):
        calls["logger"] = logger
        calls["message"] = message
        calls["fields"] = fields

    monkeypatch.setattr(audit, "log_event", fake_log_event)
    logger = object()
    audit.log_audit_event(logger, "rotate")

    assert calls["logger"] is logger
    assert calls["message"] == "audit_event"
    assert calls["fields"]["action"] == "rotate"
    assert calls["fields"]["actor"]


def test_errors_helpers() -> None:
    assert errors.status_hint(401) == "blocked"
    assert errors.status_hint(429) == "rate_limited"
    assert errors.status_hint(500) == "upstream_error"
    assert errors.status_hint(200) == "unknown"


def test_error_messages_include_guidance() -> None:
    from kmi_manager_cli.config import Config

    config = Config(
        auths_dir="auths",
        proxy_listen="127.0.0.1:54123",
        proxy_base_path="/kmi-rotor/v1",
        upstream_base_url="https://example.com",
        state_dir="state",
        dry_run=True,
        auto_rotate_allowed=False,
        rotation_cooldown_seconds=300,
        proxy_allow_remote=False,
        proxy_token="",
        proxy_max_rps=0,
        proxy_max_rpm=0,
        proxy_retry_max=0,
        proxy_retry_base_ms=250,
    )
    no_keys = errors.no_keys_message(config)
    remediation = errors.remediation_message()
    assert "No API keys found" in no_keys
    assert "Next steps" in remediation


def test_json_formatter_includes_extras() -> None:
    formatter = logging_module.JsonFormatter("UTC")
    record = logging.LogRecord(
        name="kmi",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-1"
    payload = json.loads(formatter.format(record))
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["request_id"] == "req-1"
    assert "ts" in payload
