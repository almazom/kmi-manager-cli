from __future__ import annotations

from kmi_manager_cli import robin


def test_robin_main_invokes_app(monkeypatch) -> None:
    calls = {}

    def fake_app(*, args, prog_name):
        calls["args"] = args
        calls["prog_name"] = prog_name

    monkeypatch.setattr(robin, "app", fake_app)
    monkeypatch.setattr(robin.sys, "argv", ["kimi_robin", "--help"])

    robin.main()

    assert calls["prog_name"] == "kimi_robin"
    assert calls["args"] == ["kimi", "--help"]
