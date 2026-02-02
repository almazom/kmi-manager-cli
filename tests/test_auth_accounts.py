from __future__ import annotations

from pathlib import Path

from kmi_manager_cli import auth_accounts as auth_module
from kmi_manager_cli.auth_accounts import load_accounts_from_auths_dir, load_current_account


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_load_accounts_from_auths_dir_parses_formats(tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()

    _write(
        auths_dir / "alpha_config.toml",
        "\n".join(
            [
                "[providers.kimi-for-coding]",
                'api_key = "sk-alpha"',
                'base_url = "https://example.com"',
                'email = "alpha@example.com"',
            ]
        )
        + "\n",
    )
    _write(
        auths_dir / "bravo.env",
        "\n".join(
            [
                "KMI_API_KEY=sk-bravo",
                "KMI_KEY_LABEL=bravo",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
            ]
        )
        + "\n",
    )
    _write(
        auths_dir / "charlie.json",
        "\n".join(
            [
                "{",
                '  "providers": {',
                '    "kimi-for-coding": {',
                '      "api_key": "sk-charlie",',
                '      "base_url": "https://example.com"',
                "    }",
                "  }",
                "}",
            ]
        )
        + "\n",
    )

    accounts = load_accounts_from_auths_dir(auths_dir, "https://example.com")
    by_label = {account.label: account for account in accounts}

    assert set(by_label.keys()) == {"alpha", "bravo", "charlie"}
    assert by_label["alpha"].email == "alpha@example.com"
    assert by_label["bravo"].api_key == "sk-bravo"
    assert by_label["charlie"].base_url == "https://example.com"


def test_load_current_account_uses_default_model_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    _write(
        config_path,
        "\n".join(
            [
                'default_model = "kimi-default"',
                "",
                "[models.kimi-default]",
                'provider = "moonshot-ai"',
                "",
                "[providers.moonshot-ai]",
                'api_key = "sk-current"',
                'base_url = "https://example.com"',
                'email = "owner@example.com"',
            ]
        )
        + "\n",
    )

    account = load_current_account(config_path)

    assert account is not None
    assert account.label == "current:moonshot-ai"
    assert account.api_key == "sk-current"
    assert account.email == "owner@example.com"


def test_provider_helpers_and_normalizers(tmp_path: Path) -> None:
    config = {
        "providers": {"managed:kimi-code": {"api_key": "sk-managed"}},
        "providers.kimi-for-coding": {"api_key": "sk-kimi", "base_url": "https://example.com"},
    }
    providers = auth_module._providers_from_config(config)
    name, values = auth_module._select_provider(providers)
    assert name == "managed:kimi-code"
    assert values["api_key"] == "sk-managed"
    assert auth_module._normalize_label("alpha_config") == "alpha"
    assert auth_module._normalize_name('"moonshot-ai"') == "moonshot-ai"


def test_account_from_env_email_fields(tmp_path: Path) -> None:
    env_path = tmp_path / "alpha.env"
    _write(
        env_path,
        "\n".join(
            [
                "KMI_API_KEY=sk-alpha",
                "KMI_KEY_LABEL=alpha",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
                "KMI_ACCOUNT_EMAIL=alpha@example.com",
            ]
        )
        + "\n",
    )
    account = auth_module._account_from_env(
        env_path, "https://example.com", allowlist=()
    )
    assert account is not None
    assert account.email == "alpha@example.com"


def test_account_from_json_invalid_payload(tmp_path: Path) -> None:
    json_path = tmp_path / "bad.json"
    _write(json_path, '{"bad": true}\n')
    assert (
        auth_module._account_from_json(json_path, "https://example.com", allowlist=())
        is None
    )


def test_collect_auth_files_includes_nested_files(tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    nested = auths_dir / "nested"
    nested.mkdir(parents=True)
    _write(nested / "alpha.env", "KMI_API_KEY=sk-alpha\n")
    files = auth_module.collect_auth_files(auths_dir)
    assert (nested / "alpha.env") in files


def test_copy_account_config(tmp_path: Path) -> None:
    src = tmp_path / "alpha.toml"
    dest = tmp_path / "dest" / "config.toml"
    _write(src, "key = 'value'\n")
    assert auth_module.copy_account_config(str(src), dest) is True
    assert dest.read_text(encoding="utf-8") == "key = 'value'\n"
    assert auth_module.copy_account_config(str(tmp_path / "missing.toml"), dest) is False


def test_parse_toml_invalid_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    _write(path, "not=toml=content\n")
    assert auth_module._parse_toml(path) == {}


def test_account_from_toml_email_from_filename(tmp_path: Path) -> None:
    path = tmp_path / "alpha_user@example.com.toml"
    _write(
        path,
        "\n".join(
            [
                "[providers.kimi-for-coding]",
                'api_key = "sk-alpha"',
                'base_url = "https://example.com"',
            ]
        )
        + "\n",
    )
    account = auth_module._account_from_toml(path, "https://example.com", allowlist=())
    assert account is not None
    assert account.email == "alpha_user@example.com.toml"


def test_account_from_env_missing_api_key(tmp_path: Path) -> None:
    path = tmp_path / "missing.env"
    _write(path, "KMI_KEY_LABEL=alpha\n")
    assert auth_module._account_from_env(path, "https://example.com", allowlist=()) is None


def test_account_from_json_extracts_root_email(tmp_path: Path) -> None:
    path = tmp_path / "alpha.json"
    _write(
        path,
        "\n".join(
            [
                "{",
                '  "email": "root@example.com",',
                '  "providers": {',
                '    "kimi-for-coding": {',
                '      "api_key": "sk-alpha",',
                '      "base_url": "https://example.com"',
                "    }",
                "  }",
                "}",
            ]
        )
        + "\n",
    )
    account = auth_module._account_from_json(path, "https://example.com", allowlist=())
    assert account is not None
    assert account.email == "root@example.com"


def test_load_current_account_missing_file(tmp_path: Path) -> None:
    assert auth_module.load_current_account(tmp_path / "missing.toml") is None


def test_normalize_base_url_invalid_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "alpha.env"
    _write(path, "KMI_API_KEY=sk\n")
    assert auth_module._normalize_base_url("http://example.com", "https://example.com", path, ()) is None


def test_select_provider_fallback() -> None:
    providers = {"custom": {"api_key": "sk-custom"}}
    name, values = auth_module._select_provider(providers)
    assert name == "custom"
    assert values["api_key"] == "sk-custom"


def test_extract_email_helpers() -> None:
    assert auth_module._extract_email_from_values({"note": "user@example.com"}) == "user@example.com"
    nested = {"outer": {"inner": {"email": "nested@example.com"}}}
    assert auth_module._extract_email_from_config(nested) == "nested@example.com"


def test_load_accounts_from_auths_dir_json_bak(tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    _write(
        auths_dir / "alpha.json.bak",
        "\n".join(
            [
                "{",
                '  "providers": {',
                '    "kimi-for-coding": {',
                '      "api_key": "sk-alpha",',
                '      "base_url": "https://example.com"',
                "    }",
                "  }",
                "}",
            ]
        )
        + "\n",
    )
    accounts = auth_module.load_accounts_from_auths_dir(auths_dir, "https://example.com")
    assert len(accounts) == 1


def test_load_accounts_from_auths_dir_ignores_unknown(tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    _write(auths_dir / "alpha.txt", "ignored\n")
    accounts = auth_module.load_accounts_from_auths_dir(auths_dir, "https://example.com")
    assert accounts == []


def test_select_provider_returns_none_when_missing_api_key() -> None:
    providers = {"alpha": {"api_key": ""}}
    assert auth_module._select_provider(providers) is None


def test_providers_from_config_skips_non_dict_entries() -> None:
    config = {
        "providers": {"bad": "nope"},
        "providers.alpha": "skip",
        "providers.beta": {"api_key": "sk-beta"},
        "other": {"api_key": "sk-other"},
    }
    providers = auth_module._providers_from_config(config)
    assert "bad" not in providers
    assert "alpha" not in providers
    assert "beta" in providers


def test_extract_email_from_config_skips_non_dict_values() -> None:
    assert auth_module._extract_email_from_config({"outer": ["nope"]}) is None


def test_account_from_toml_missing_provider_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "alpha.toml"
    _write(path, "[providers.kimi-for-coding]\nbase_url='https://example.com'\n")
    assert auth_module._account_from_toml(path, "https://example.com", allowlist=()) is None


def test_account_from_toml_invalid_base_url_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "alpha.toml"
    _write(
        path,
        "\n".join(
            [
                "[providers.kimi-for-coding]",
                'api_key = "sk-alpha"',
                'base_url = "http://example.com"',
            ]
        )
        + "\n",
    )
    assert auth_module._account_from_toml(path, "https://example.com", allowlist=()) is None


def test_account_from_toml_missing_api_key_branch(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "alpha.toml"
    _write(path, "[providers.kimi-for-coding]\n")
    monkeypatch.setattr(auth_module, "_select_provider", lambda _p: ("x", {"api_key": ""}))
    assert auth_module._account_from_toml(path, "https://example.com", allowlist=()) is None


def test_account_from_json_invalid_json_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    _write(path, "{broken")
    assert auth_module._account_from_json(path, "https://example.com", allowlist=()) is None


def test_account_from_json_skips_non_dict_provider(tmp_path: Path) -> None:
    path = tmp_path / "alpha.json"
    _write(
        path,
        "\n".join(
            [
                "{",
                '  "providers": {',
                '    "bad": "nope",',
                '    "kimi-for-coding": {',
                '      "api_key": "sk-alpha",',
                '      "base_url": "https://example.com"',
                "    }",
                "  }",
                "}",
            ]
        )
        + "\n",
    )
    account = auth_module._account_from_json(path, "https://example.com", allowlist=())
    assert account is not None
    assert account.api_key == "sk-alpha"


def test_account_from_json_no_valid_provider(tmp_path: Path) -> None:
    path = tmp_path / "alpha.json"
    _write(path, '{"providers": {"kimi-for-coding": {"base_url": "https://example.com"}}}\n')
    assert auth_module._account_from_json(path, "https://example.com", allowlist=()) is None


def test_account_from_json_invalid_base_url_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "alpha.json"
    _write(
        path,
        "\n".join(
            [
                "{",
                '  "providers": {',
                '    "kimi-for-coding": {',
                '      "api_key": "sk-alpha",',
                '      "base_url": "http://example.com"',
                "    }",
                "  }",
                "}",
            ]
        )
        + "\n",
    )
    assert auth_module._account_from_json(path, "https://example.com", allowlist=()) is None


def test_account_from_json_missing_api_key_branch(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "alpha.json"
    _write(path, '{"providers": {"kimi-for-coding": {"base_url": "https://example.com"}}}\n')
    monkeypatch.setattr(auth_module, "_select_provider", lambda _p: ("x", {"api_key": ""}))
    assert auth_module._account_from_json(path, "https://example.com", allowlist=()) is None


def test_collect_auth_files_includes_root_files(tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    root_file = auths_dir / "alpha.env"
    _write(root_file, "KMI_API_KEY=sk-alpha\n")
    files = auth_module.collect_auth_files(auths_dir)
    assert root_file in files


def test_load_accounts_from_auths_dir_missing_returns_empty(tmp_path: Path) -> None:
    assert auth_module.load_accounts_from_auths_dir(tmp_path / "missing", "https://example.com") == []


def test_load_current_account_default_model_missing_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    _write(
        config_path,
        "\n".join(
            [
                'default_model = "kimi-default"',
                "",
                '[providers."managed:kimi-code"]',
                'api_key = "sk-current"',
                'base_url = "https://example.com"',
            ]
        )
        + "\n",
    )
    account = auth_module.load_current_account(config_path)
    assert account is not None
    assert account.label == "current:managed:kimi-code"


def test_load_current_account_missing_base_url(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    _write(
        config_path,
        "\n".join(
            [
                "[providers.managed:kimi-code]",
                'api_key = "sk-current"',
            ]
        )
        + "\n",
    )
    assert auth_module.load_current_account(config_path) is None


def test_load_current_account_invalid_base_url(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    _write(
        config_path,
        "\n".join(
            [
                "[providers.managed:kimi-code]",
                'api_key = "sk-current"',
                'base_url = "http://example.com"',
            ]
        )
        + "\n",
    )
    assert auth_module.load_current_account(config_path) is None


def test_load_current_account_email_from_root_and_text(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    _write(
        config_path,
        "\n".join(
            [
                'email = "root@example.com"',
                "",
                '[providers."managed:kimi-code"]',
                'api_key = "sk-current"',
                'base_url = "https://example.com"',
            ]
        )
        + "\n",
    )
    account = auth_module.load_current_account(config_path)
    assert account is not None
    assert account.email == "root@example.com"

    config_path_text = tmp_path / "config-text.toml"
    _write(
        config_path_text,
        "\n".join(
            [
                "# contact support@example.com",
                '[providers."managed:kimi-code"]',
                'api_key = "sk-current"',
                'base_url = "https://example.com"',
            ]
        )
        + "\n",
    )
    account_text = auth_module.load_current_account(config_path_text)
    assert account_text is not None
    assert account_text.email == "support@example.com"


def test_account_from_env_invalid_base_url(tmp_path: Path) -> None:
    path = tmp_path / "alpha.env"
    _write(
        path,
        "\n".join(
            [
                "KMI_API_KEY=sk-alpha",
                "KMI_KEY_LABEL=alpha",
                "KMI_UPSTREAM_BASE_URL=http://example.com",
            ]
        )
        + "\n",
    )
    assert auth_module._account_from_env(path, "https://example.com", allowlist=()) is None


def test_load_current_account_missing_provider(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _write(path, 'default_model = "missing"\n')
    assert auth_module.load_current_account(path) is None
