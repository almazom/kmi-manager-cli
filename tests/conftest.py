"""Shared pytest fixtures for KMI Manager CLI tests."""

from pathlib import Path
from typing import Callable

import pytest

from kmi_manager_cli.config import Config


@pytest.fixture
def make_config(tmp_path: Path) -> Callable[..., Config]:
    """Factory fixture to create Config instances with test defaults.
    
    Usage:
        def test_something(make_config):
            config = make_config(dry_run=True)
            # or with overrides
            config = make_config(proxy_max_rps=100, upstream_base_url="https://custom.com")
    """
    def _factory(**overrides) -> Config:
        defaults = {
            "auths_dir": tmp_path,
            "proxy_listen": "127.0.0.1:54123",
            "proxy_base_path": "/kmi-rotor/v1",
            "upstream_base_url": "https://example.com",
            "state_dir": tmp_path,
            "dry_run": True,
            "auto_rotate_allowed": True,
            "rotation_cooldown_seconds": 300,
            "proxy_allow_remote": False,
            "proxy_token": "",
            "proxy_max_rps": 0,
            "proxy_max_rpm": 0,
            "proxy_retry_max": 0,
            "proxy_retry_base_ms": 250,
            "env_path": None,
            "enforce_file_perms": False,
        }
        defaults.update(overrides)
        return Config(**defaults)
    return _factory
