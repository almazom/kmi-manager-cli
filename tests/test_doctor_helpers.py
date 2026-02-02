from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from kmi_manager_cli import doctor as doctor_module
from kmi_manager_cli.config import Config
from kmi_manager_cli.health import Usage
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import KeyState, State


def _make_config(tmp_path: Path) -> Config:
    return Config(
        auths_dir=tmp_path / "auths",
        proxy_listen="127.0.0.1:9999",
        proxy_base_path="/kmi-rotor/v1",
        upstream_base_url="https://example.com",
        state_dir=tmp_path,
        dry_run=True,
        auto_rotate_allowed=False,
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


def test_format_age() -> None:
    assert doctor_module._format_age(-1) == "just now"
    assert doctor_module._format_age(30) == "30s ago"
    assert doctor_module._format_age(90) == "1m ago"
    assert doctor_module._format_age(7200) == "2h ago"


def test_status_badge_default() -> None:
    assert doctor_module._status_badge("unknown") == ("•", "white")


def test_proxy_listening_true(monkeypatch) -> None:
    class DummySocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(doctor_module.socket, "create_connection", lambda *_a, **_k: DummySocket())
    assert doctor_module._proxy_listening("127.0.0.1", 1234) is True


def test_normalize_connect_host() -> None:
    assert doctor_module._normalize_connect_host("0.0.0.0") == "127.0.0.1"


def test_file_status_missing(tmp_path: Path) -> None:
    check = doctor_module._file_status(tmp_path / "missing.txt", "Trace")
    assert check.status == "warn"


def test_file_status_ok(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text("data\n", encoding="utf-8")
    check = doctor_module._file_status(path, "Trace")
    assert check.status == "ok"
    assert "updated" in check.details


def test_check_env(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    assert doctor_module._check_env(config).status == "info"
    config = Config(**{**config.__dict__, "env_path": tmp_path / ".env"})
    assert doctor_module._check_env(config).status == "ok"


def test_check_auths(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    config.auths_dir.mkdir(parents=True)
    check = doctor_module._check_auths(config)
    assert check.status == "fail"

    (config.auths_dir / "alpha.env").write_text(
        "KMI_API_KEY=sk-test\nKMI_KEY_LABEL=alpha\nKMI_UPSTREAM_BASE_URL=https://example.com\n",
        encoding="utf-8",
    )
    check = doctor_module._check_auths(config)
    assert check.status == "ok"
    assert "alpha" in check.details


def test_check_proxy_failures(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    config = Config(**{**config.__dict__, "proxy_listen": "10.0.0.1:9999"})
    check = doctor_module._check_proxy(config)
    assert check.status == "fail"

    config = Config(
        **{
            **config.__dict__,
            "proxy_allow_remote": True,
            "proxy_require_tls": True,
            "proxy_tls_terminated": False,
        }
    )
    check = doctor_module._check_proxy(config)
    assert check.status == "fail"

    config = Config(
        **{
            **config.__dict__,
            "proxy_tls_terminated": True,
            "proxy_token": "",
        }
    )
    check = doctor_module._check_proxy(config)
    assert check.status == "fail"

    monkeypatch.setattr(doctor_module, "_proxy_listening", lambda *_args, **_kwargs: False)
    config = Config(
        **{
            **config.__dict__,
            "proxy_listen": "127.0.0.1:9999",
            "proxy_allow_remote": False,
            "proxy_token": "token",
        }
    )
    check = doctor_module._check_proxy(config)
    assert check.status == "warn"


def test_check_proxy_ok_when_listening(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    monkeypatch.setattr(doctor_module, "_proxy_listening", lambda *_a, **_k: True)
    check = doctor_module._check_proxy(config)
    assert check.status == "ok"


def test_check_kimi_env(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    monkeypatch.delenv("KIMI_BASE_URL", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    assert doctor_module._check_kimi_env(config).status == "warn"

    monkeypatch.setenv("KIMI_BASE_URL", "https://wrong")
    assert doctor_module._check_kimi_env(config).status == "warn"

    monkeypatch.setenv("KIMI_BASE_URL", doctor_module._proxy_base_url(config))
    monkeypatch.setenv("KIMI_API_KEY", "proxy")
    assert doctor_module._check_kimi_env(config).status == "ok"


def test_check_kimi_env_missing_api_key(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    monkeypatch.setenv("KIMI_BASE_URL", doctor_module._proxy_base_url(config))
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    assert doctor_module._check_kimi_env(config).status == "warn"


def test_check_state(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    check = doctor_module._check_state(config)
    assert check.status == "warn"

    state_path = tmp_path / "state.json"
    state_path.write_text("not-json", encoding="utf-8")
    check = doctor_module._check_state(config)
    assert check.status == "fail"

    state_path.write_text(json.dumps({"auto_rotate": True}), encoding="utf-8")
    check = doctor_module._check_state(config)
    assert check.status == "info"


def test_check_permissions(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    monkeypatch.setattr(doctor_module, "_collect_insecure", lambda _paths: ["a", "b", "c", "d"])
    check = doctor_module._check_permissions(config)
    assert check.status == "warn"
    assert "insecure" in check.details


def test_recheck_blocked_keys(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")])
    state = State(keys={"a": KeyState(blocked_reason="payment_required")})

    monkeypatch.setattr(
        doctor_module,
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
    cleared, remaining = doctor_module._recheck_blocked_keys(config, registry, state)
    assert cleared == 1
    assert remaining == 0

    monkeypatch.setattr(doctor_module, "fetch_usage", lambda *_args, **_kwargs: None)
    state.keys["a"].blocked_reason = "payment_required"
    cleared, remaining = doctor_module._recheck_blocked_keys(config, registry, state)
    assert cleared == 0
    assert remaining == 1


def test_run_doctor_uses_checks(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    monkeypatch.setattr(
        doctor_module,
        "collect_checks",
        lambda _config: [
            doctor_module.DoctorCheck("A", "ok", "ok"),
            doctor_module.DoctorCheck("B", "fail", "bad"),
        ],
    )
    monkeypatch.setattr(
        doctor_module,
        "get_console",
        lambda: SimpleNamespace(print=lambda *args, **kwargs: None),
    )
    code = doctor_module.run_doctor(config)
    assert code == 1


def test_run_doctor_clear_blocklist(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    monkeypatch.setattr(
        doctor_module,
        "collect_checks",
        lambda _config: [doctor_module.DoctorCheck("A", "ok", "ok", fix="do")],
    )
    monkeypatch.setattr(
        doctor_module,
        "get_console",
        lambda: SimpleNamespace(print=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(doctor_module, "load_auths_dir", lambda *_a, **_k: Registry(keys=[]))
    monkeypatch.setattr(doctor_module, "load_state", lambda *_a, **_k: State())
    monkeypatch.setattr(doctor_module, "clear_blocked", lambda *_a, **_k: 1)
    monkeypatch.setattr(doctor_module, "save_state", lambda *_a, **_k: None)
    code = doctor_module.run_doctor(config, clear_blocklist=True)
    assert code == 0


def test_run_doctor_recheck_keys(monkeypatch, tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    monkeypatch.setattr(
        doctor_module,
        "collect_checks",
        lambda _config: [doctor_module.DoctorCheck("A", "ok", "ok")],
    )
    monkeypatch.setattr(
        doctor_module,
        "get_console",
        lambda: SimpleNamespace(print=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(doctor_module, "load_auths_dir", lambda *_a, **_k: Registry(keys=[]))
    monkeypatch.setattr(doctor_module, "load_state", lambda *_a, **_k: State())
    monkeypatch.setattr(doctor_module, "_recheck_blocked_keys", lambda *_a, **_k: (1, 0))
    monkeypatch.setattr(doctor_module, "save_state", lambda *_a, **_k: None)
    code = doctor_module.run_doctor(config, recheck_keys=True)
    assert code == 0
