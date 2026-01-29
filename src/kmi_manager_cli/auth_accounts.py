from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values


@dataclass
class Account:
    id: str
    label: str
    api_key: str
    base_url: str
    source: str
    email: Optional[str] = None


_PROVIDER_ORDER = ["managed:kimi-code", "kimi-for-coding", "moonshot-ai"]
_SECTION_RE = re.compile(r"^\[(.+)\]$")
_KV_RE = re.compile(r"^([A-Za-z0-9_\-\.\" ]+)\s*=\s*(.+)$")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _normalize_label(label: str) -> str:
    value = label.strip()
    value = re.sub(r"([_-]?config)$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[_-]+$", "", value)
    return value or label


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _normalize_name(name: str) -> str:
    name = name.strip()
    if name.startswith('"') and name.endswith('"'):
        return name[1:-1]
    return name


def _parse_toml(path: Path) -> dict[str, dict[str, str]]:
    section = "__root__"
    config: dict[str, dict[str, str]] = {"__root__": {}}
    for line in path.read_text(errors="ignore").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        m = _SECTION_RE.match(raw)
        if m:
            section = m.group(1)
            config.setdefault(section, {})
            continue
        kv = _KV_RE.match(raw)
        if not kv:
            continue
        key = kv.group(1).strip().strip('"')
        value = _strip_quotes(kv.group(2))
        if section is None:
            section = "__root__"
            config.setdefault(section, {})
        config[section][key] = value
    return config


def _providers_from_config(config: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    providers: dict[str, dict[str, str]] = {}
    for section, values in config.items():
        if not section.startswith("providers."):
            continue
        name = _normalize_name(section.split(".", 1)[1])
        providers[name] = values
    return providers


def _select_provider(providers: dict[str, dict[str, str]]) -> Optional[tuple[str, dict[str, str]]]:
    for name in _PROVIDER_ORDER:
        if name in providers and providers[name].get("api_key"):
            return name, providers[name]
    for name, values in providers.items():
        if values.get("api_key"):
            return name, values
    return None


def _extract_email_from_values(values: dict[str, str]) -> Optional[str]:
    for key in ("email", "account_email", "user_email", "login_email", "user", "account"):
        value = values.get(key)
        if value and _EMAIL_RE.search(str(value)):
            return _EMAIL_RE.search(str(value)).group(0)
    for value in values.values():
        if value and _EMAIL_RE.search(str(value)):
            return _EMAIL_RE.search(str(value)).group(0)
    return None


def _extract_email_from_config(config: dict[str, dict[str, str]]) -> Optional[str]:
    for values in config.values():
        if not isinstance(values, dict):
            continue
        email = _extract_email_from_values(values)
        if email:
            return email
    return None


def _extract_email_from_text(text: str) -> Optional[str]:
    match = _EMAIL_RE.search(text)
    if match:
        return match.group(0)
    return None


def _account_from_toml(path: Path, default_base_url: str) -> Optional[Account]:
    config = _parse_toml(path)
    providers = _providers_from_config(config)
    selected = _select_provider(providers)
    if not selected:
        return None
    provider_name, values = selected
    api_key = values.get("api_key")
    if not api_key:
        return None
    base_url = (values.get("base_url") or default_base_url).rstrip("/")
    label = _normalize_label(path.stem)
    email = _extract_email_from_values(values)
    if email is None:
        email = _extract_email_from_config(config)
    if email is None:
        email = _extract_email_from_text(path.name) or _extract_email_from_text(path.read_text(errors="ignore"))
    return Account(
        id=f"auth:{path.name}",
        label=label,
        api_key=api_key,
        base_url=base_url,
        source=str(path),
        email=email,
    )


def _account_from_env(path: Path, default_base_url: str) -> Optional[Account]:
    data = dotenv_values(path)
    api_key = data.get("KMI_API_KEY")
    if not api_key:
        return None
    label = _normalize_label(str(data.get("KMI_KEY_LABEL") or path.stem))
    base_url = (data.get("KMI_UPSTREAM_BASE_URL") or default_base_url).rstrip("/")
    email = None
    for key in ("KMI_ACCOUNT_EMAIL", "KMI_EMAIL", "EMAIL"):
        value = data.get(key)
        if value and _EMAIL_RE.search(str(value)):
            email = _EMAIL_RE.search(str(value)).group(0)
            break
    if email is None:
        email = _extract_email_from_values({k: str(v) for k, v in data.items() if v is not None})
    if email is None:
        email = _extract_email_from_text(path.name)
    return Account(
        id=f"auth:{path.name}",
        label=str(label),
        api_key=str(api_key),
        base_url=str(base_url),
        source=str(path),
        email=email,
    )


def _account_from_json(path: Path, default_base_url: str) -> Optional[Account]:
    try:
        payload = json.loads(path.read_text(errors="ignore"))
    except json.JSONDecodeError:
        return None
    providers = payload.get("providers") if isinstance(payload, dict) else None
    if not isinstance(providers, dict):
        return None
    normalized: dict[str, dict[str, str]] = {}
    for name, values in providers.items():
        if isinstance(values, dict):
            normalized[str(name)] = {k: str(v) for k, v in values.items()}
    selected = _select_provider(normalized)
    if not selected:
        return None
    provider_name, values = selected
    api_key = values.get("api_key")
    if not api_key:
        return None
    base_url = (values.get("base_url") or default_base_url).rstrip("/")
    label = _normalize_label(path.stem)
    email = _extract_email_from_values(values)
    if email is None and isinstance(payload, dict):
        root_values = {k: str(v) for k, v in payload.items() if isinstance(v, (str, int, float))}
        email = _extract_email_from_values(root_values)
    if email is None:
        email = _extract_email_from_text(path.name)
    return Account(
        id=f"auth:{path.name}",
        label=label,
        api_key=api_key,
        base_url=base_url,
        source=str(path),
        email=email,
    )


def load_accounts_from_auths_dir(auths_dir: Path, default_base_url: str) -> list[Account]:
    auths_dir = auths_dir.expanduser()
    if not auths_dir.exists():
        return []
    accounts: list[Account] = []
    candidates: list[Path] = []
    for path in sorted(auths_dir.iterdir()):
        if path.is_dir():
            candidates.extend(sorted([p for p in path.iterdir() if p.is_file()]))
        elif path.is_file():
            candidates.append(path)
    for path in candidates:
        if path.suffix.lower() == ".env":
            account = _account_from_env(path, default_base_url)
        elif path.suffix.lower() == ".toml":
            account = _account_from_toml(path, default_base_url)
        elif path.suffix.lower() in {".json", ".bak"} or path.name.endswith(".json.bak"):
            account = _account_from_json(path, default_base_url)
        else:
            account = None
        if account:
            accounts.append(account)
    return accounts


def load_current_account(config_path: Path) -> Optional[Account]:
    if not config_path.exists():
        return None
    config = _parse_toml(config_path)
    root = config.get("__root__", {})
    default_model = root.get("default_model") if root else None

    provider_name = None
    if default_model:
        model_section = f"models.{default_model}"
        model = config.get(model_section)
        if model and model.get("provider"):
            provider_name = _normalize_name(model.get("provider", ""))
    if provider_name is None:
        provider_name = _PROVIDER_ORDER[0]

    providers = _providers_from_config(config)
    values = providers.get(provider_name)
    if not values:
        return None
    api_key = values.get("api_key")
    base_url = values.get("base_url")
    if not api_key or not base_url:
        return None
    base_url = base_url.rstrip("/")
    label = f"current:{provider_name}"
    email = _extract_email_from_values(values)
    if email is None:
        email = _extract_email_from_values(root)
    if email is None:
        email = _extract_email_from_text(config_path.read_text(errors="ignore"))
    return Account(
        id="current",
        label=label,
        api_key=api_key,
        base_url=base_url,
        source=str(config_path),
        email=email,
    )


def resolve_provider_name(config_path: Path) -> str:
    if not config_path.exists():
        return _PROVIDER_ORDER[0]
    config = _parse_toml(config_path)
    root = config.get("__root__", {})
    default_model = root.get("default_model") if root else None

    provider_name = None
    if default_model:
        model_section = f"models.{default_model}"
        model = config.get(model_section)
        if model and model.get("provider"):
            provider_name = _normalize_name(model.get("provider", ""))
    if provider_name is None:
        provider_name = _PROVIDER_ORDER[0]
    return provider_name


def update_provider_config(config_path: Path, provider_name: str, api_key: str, base_url: str) -> bool:
    config_path = config_path.expanduser()
    if not config_path.exists():
        return False

    lines = config_path.read_text(errors="ignore").splitlines()
    header_re = re.compile(r"^\\s*\\[providers\\.(\"?)(.+?)\\1\\]\\s*$")
    start = None
    for idx, line in enumerate(lines):
        match = header_re.match(line)
        if not match:
            continue
        name = _normalize_name(match.group(2))
        if name == provider_name:
            start = idx
            break

    def _needs_quotes(value: str) -> bool:
        return not re.match(r"^[A-Za-z0-9_-]+$", value)

    if start is None:
        header = f'[providers.\"{provider_name}\"]' if _needs_quotes(provider_name) else f'[providers.{provider_name}]'
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(
            [
                header,
                'type = \"kimi\"',
                f'base_url = \"{base_url}\"',
                f'api_key = \"{api_key}\"',
            ]
        )
        config_path.write_text("\n".join(lines) + "\n")
        return True

    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].lstrip().startswith("["):
            end = idx
            break

    found_base = False
    found_key = False
    for idx in range(start + 1, end):
        if re.match(r"^\\s*base_url\\s*=", lines[idx]):
            lines[idx] = f'base_url = \"{base_url}\"'
            found_base = True
        elif re.match(r"^\\s*api_key\\s*=", lines[idx]):
            lines[idx] = f'api_key = \"{api_key}\"'
            found_key = True

    insert_at = end
    if not found_base:
        lines.insert(insert_at, f'base_url = \"{base_url}\"')
        insert_at += 1
        end += 1
    if not found_key:
        lines.insert(insert_at, f'api_key = \"{api_key}\"')

    config_path.write_text("\n".join(lines) + "\n")
    return True
