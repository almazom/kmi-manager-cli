from __future__ import annotations

from pathlib import Path

from kmi_manager_cli.auth_accounts import resolve_provider_name, update_provider_config


def _write_config(path: Path) -> None:
    path.write_text(
        """
DEFAULT = "noop"
default_model = "kimi-code/kimi-for-coding"

[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"

[providers."managed:kimi-code"]
type = "kimi"
base_url = "https://old.example.com"
api_key = "sk-old"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_resolve_provider_name(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    _write_config(config_path)
    provider = resolve_provider_name(config_path)
    assert provider == "managed:kimi-code"


def test_update_provider_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    _write_config(config_path)
    assert update_provider_config(
        config_path,
        provider_name="managed:kimi-code",
        api_key="sk-new",
        base_url="https://new.example.com",
    )
    content = config_path.read_text(encoding="utf-8")
    assert "base_url = \"https://new.example.com\"" in content
    assert "api_key = \"sk-new\"" in content


def test_update_provider_config_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "missing.toml"
    assert update_provider_config(config_path, "managed:kimi-code", "sk-new", "https://new.example.com") is False
