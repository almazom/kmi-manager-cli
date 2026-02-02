from __future__ import annotations

from pathlib import Path

import pytest

from kmi_manager_cli import config as config_module


def test_parse_bool_variants() -> None:
    assert config_module._parse_bool(None, True) is True
    assert config_module._parse_bool(None, False) is False
    for value in ("1", "true", "yes", "on", " TRUE "):
        assert config_module._parse_bool(value, False) is True
    assert config_module._parse_bool("0", True) is False


def test_require_non_empty_raises() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        config_module._require_non_empty("KMI_PROXY_LISTEN", "  ")


def test_parse_allowlist_and_host_allowed() -> None:
    assert config_module._parse_allowlist("") == ()
    allowlist = config_module._parse_allowlist("api.kimi.com, *.kimi.com")
    assert config_module._host_allowed("api.kimi.com", allowlist) is True
    assert config_module._host_allowed("sub.kimi.com", allowlist) is True
    assert config_module._host_allowed("other.com", allowlist) is False


def test_validate_base_url_requires_host() -> None:
    with pytest.raises(ValueError, match="include a host"):
        config_module.validate_base_url("base_url", "https:///path", ())


def test_resolve_env_path_override(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    monkeypatch.setenv("KMI_ENV_PATH", str(env_path))
    resolved = config_module._resolve_env_path()
    assert resolved == env_path


def test_resolve_env_path_falls_back_to_dotenv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KMI_ENV_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("KMI_PROXY_LISTEN=127.0.0.1:1\n", encoding="utf-8")
    resolved = config_module._resolve_env_path()
    assert resolved == Path(".env")


def test_resolve_auths_dir_prefers_env(monkeypatch, tmp_path: Path) -> None:
    env_dir = tmp_path / "auths"
    env_dir.mkdir()
    monkeypatch.setenv("KMI_AUTHS_DIR", str(env_dir))
    assert config_module._resolve_auths_dir() == env_dir


def test_resolve_auths_dir_uses_default_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KMI_AUTHS_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / config_module.DEFAULT_KMI_AUTHS_DIR).mkdir()
    assert config_module._resolve_auths_dir() == Path(config_module.DEFAULT_KMI_AUTHS_DIR)


def test_resolve_auths_dir_uses_home_candidate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KMI_AUTHS_DIR", raising=False)
    home_candidate = Path("~/.kimi/_auths").expanduser()

    orig_exists = config_module.Path.exists

    def fake_exists(self: Path) -> bool:
        if str(self) == str(Path(config_module.DEFAULT_KMI_AUTHS_DIR).expanduser()):
            return False
        if str(self) == str(home_candidate):
            return True
        return orig_exists(self)

    monkeypatch.setattr(config_module.Path, "exists", fake_exists, raising=False)

    assert config_module._resolve_auths_dir() == home_candidate


def test_resolve_auths_dir_falls_back_to_default_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("KMI_AUTHS_DIR", raising=False)
    default_path = Path(config_module.DEFAULT_KMI_AUTHS_DIR).expanduser()
    home_candidate = Path("~/.kimi/_auths").expanduser()

    def fake_exists(self: Path) -> bool:
        if str(self) in {str(default_path), str(home_candidate)}:
            return False
        return False

    monkeypatch.setattr(config_module.Path, "exists", fake_exists, raising=False)
    assert config_module._resolve_auths_dir() == default_path


def test_load_config_calls_load_dotenv_without_env_path(monkeypatch, tmp_path: Path) -> None:
    calls = {}

    monkeypatch.delenv("KMI_ENV_PATH", raising=False)
    monkeypatch.setattr(config_module, "_resolve_env_path", lambda: None)
    monkeypatch.setattr(config_module, "_resolve_auths_dir", lambda: tmp_path)

    def fake_load_dotenv(path=None, override=False):
        calls["path"] = path
        calls["override"] = override

    monkeypatch.setattr(config_module, "load_dotenv", fake_load_dotenv)

    config_module.load_config(env_path=None)
    assert calls["path"] is None
