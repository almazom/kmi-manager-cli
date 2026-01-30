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
