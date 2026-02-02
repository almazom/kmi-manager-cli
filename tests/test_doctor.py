from __future__ import annotations

from pathlib import Path

from kmi_manager_cli.config import Config
from kmi_manager_cli.doctor import collect_checks


def _config(tmp_path: Path, auths_dir: Path) -> Config:
    return Config(
        auths_dir=auths_dir,
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
    )


def test_doctor_fails_when_no_keys(tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    checks = collect_checks(_config(tmp_path, auths_dir))
    auth_check = next(check for check in checks if check.name == "Auth keys")
    assert auth_check.status == "fail"


def test_doctor_ok_when_keys_present(tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    (auths_dir / "alpha.env").write_text(
        "KMI_API_KEY=sk-test\nKMI_KEY_LABEL=alpha\n",
        encoding="utf-8",
    )
    checks = collect_checks(_config(tmp_path, auths_dir))
    assert all(check.status != "fail" for check in checks)
