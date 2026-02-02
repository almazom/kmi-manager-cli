from __future__ import annotations

from pathlib import Path

import pytest

from kmi_manager_cli.config import (
    DEFAULT_KMI_AUTHS_DIR,
    DEFAULT_KMI_PROXY_BASE_PATH,
    DEFAULT_KMI_PROXY_LISTEN,
    DEFAULT_KMI_STATE_DIR,
    DEFAULT_KMI_UPSTREAM_BASE_URL,
    load_config,
)


def test_config_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KMI_AUTHS_DIR", raising=False)
    monkeypatch.delenv("KMI_PROXY_LISTEN", raising=False)
    monkeypatch.delenv("KMI_PROXY_BASE_PATH", raising=False)
    monkeypatch.delenv("KMI_UPSTREAM_BASE_URL", raising=False)
    monkeypatch.delenv("KMI_STATE_DIR", raising=False)

    monkeypatch.chdir(tmp_path)
    (tmp_path / DEFAULT_KMI_AUTHS_DIR).mkdir()

    cfg = load_config(env_path=tmp_path / "missing.env")

    assert cfg.auths_dir == Path(DEFAULT_KMI_AUTHS_DIR)
    assert cfg.proxy_listen == DEFAULT_KMI_PROXY_LISTEN
    assert cfg.proxy_base_path == DEFAULT_KMI_PROXY_BASE_PATH
    assert cfg.upstream_base_url == DEFAULT_KMI_UPSTREAM_BASE_URL
    assert cfg.state_dir == Path(DEFAULT_KMI_STATE_DIR).expanduser()


def test_upstream_base_url_requires_https(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KMI_UPSTREAM_BASE_URL", "http://example.com")
    monkeypatch.chdir(tmp_path)
    (tmp_path / DEFAULT_KMI_AUTHS_DIR).mkdir()

    with pytest.raises(ValueError, match="https"):
        load_config(env_path=tmp_path / "missing.env")


def test_upstream_allowlist_blocks_untrusted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KMI_UPSTREAM_BASE_URL", "https://evil.example.com")
    monkeypatch.setenv("KMI_UPSTREAM_ALLOWLIST", "api.kimi.com,*.kimi.com")
    monkeypatch.chdir(tmp_path)
    (tmp_path / DEFAULT_KMI_AUTHS_DIR).mkdir()

    with pytest.raises(ValueError, match="ALLOWLIST"):
        load_config(env_path=tmp_path / "missing.env")


def test_env_path_overrides_existing_env(monkeypatch, tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "KMI_PROXY_LISTEN=127.0.0.1:9999",
                "KMI_PROXY_BASE_PATH=/kmi-rotor/v1",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
                f"KMI_AUTHS_DIR={auths_dir}",
                f"KMI_STATE_DIR={tmp_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Set conflicting environment values to ensure env_file overrides them.
    monkeypatch.setenv("KMI_PROXY_LISTEN", "0.0.0.0:1")
    monkeypatch.setenv("KMI_PROXY_BASE_PATH", "/wrong")
    monkeypatch.setenv("KMI_UPSTREAM_BASE_URL", "https://wrong.example.com")
    monkeypatch.setenv("KMI_AUTHS_DIR", "/tmp/other-auths")
    monkeypatch.setenv("KMI_STATE_DIR", "/tmp/other-state")

    cfg = load_config(env_path=env_file)

    assert cfg.proxy_listen == "127.0.0.1:9999"
    assert cfg.proxy_base_path == "/kmi-rotor/v1"
    assert cfg.upstream_base_url == "https://example.com"
    assert cfg.auths_dir == auths_dir
    assert cfg.state_dir == tmp_path


def test_proxy_base_path_requires_leading_slash(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KMI_PROXY_BASE_PATH", "kmi")
    monkeypatch.chdir(tmp_path)
    (tmp_path / DEFAULT_KMI_AUTHS_DIR).mkdir()

    with pytest.raises(ValueError, match="KMI_PROXY_BASE_PATH"):
        load_config(env_path=tmp_path / "missing.env")


def test_allowlist_wildcard_allows_host(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KMI_UPSTREAM_BASE_URL", "https://api.kimi.com/coding/v1")
    monkeypatch.setenv("KMI_UPSTREAM_ALLOWLIST", "*.kimi.com")
    monkeypatch.chdir(tmp_path)
    (tmp_path / DEFAULT_KMI_AUTHS_DIR).mkdir()

    cfg = load_config(env_path=tmp_path / "missing.env")
    assert cfg.upstream_base_url == "https://api.kimi.com/coding/v1"
