from __future__ import annotations

from types import SimpleNamespace

import httpx

from kmi_manager_cli import health as health_module


def test_extract_remaining_percent_variants() -> None:
    assert health_module._extract_remaining_percent({"remaining_percent": "25"}) == 25.0
    assert health_module._extract_remaining_percent({"remaining": 2, "total": 4}) == 50.0
    assert (
        health_module._extract_remaining_percent({"data": {"remaining": 1, "total": 2}})
        == 50.0
    )
    assert health_module._extract_remaining_percent({"data": {}}) is None


def test_parse_limits_with_window_label() -> None:
    payload = {
        "limits": [
            {
                "detail": {"used": 5, "limit": 10, "remaining": 5, "reset_in": 3600},
                "window": {"duration": 2, "timeUnit": "HOUR"},
            }
        ]
    }
    limits = health_module._parse_limits(payload)
    assert len(limits) == 1
    assert limits[0].label == "2h limit"
    assert limits[0].used == 5
    assert limits[0].limit == 10
    assert limits[0].remaining == 5
    assert limits[0].reset_hint == "resets in 3600s"


def test_extract_email_from_payload() -> None:
    payload = {"account": {"user_email": "alpha@example.com"}}
    assert health_module._extract_email_from_payload(payload) == "alpha@example.com"


def test_fetch_usage_computes_remaining_percent(monkeypatch) -> None:
    payload = {"usage": {"used": 20, "limit": 100}}

    class DummyResponse:
        def __init__(self) -> None:
            self.content = b"{}"

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    def fake_get(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr(httpx, "get", fake_get)

    usage = health_module.fetch_usage(
        "https://example.com",
        "sk-test",
        dry_run=False,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
    )

    assert usage is not None
    assert usage.remaining_percent == 80.0
    assert usage.limit == 100
    assert usage.used == 20
