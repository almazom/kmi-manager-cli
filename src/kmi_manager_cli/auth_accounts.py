from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

from kmi_manager_cli.config import validate_base_url

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - py<3.11 fallback
    import tomli as tomllib


@dataclass
class Account:
    id: str
    label: str
    api_key: str
    base_url: str
    source: str
    email: Optional[str] = None


_PROVIDER_ORDER = ["managed:kimi-code", "kimi-for-coding", "moonshot-ai"]
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _normalize_label(label: str) -> str:
    value = label.strip()
    value = re.sub(r"([_-]?config)$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[_-]+$", "", value)
    return value or label


def _normalize_name(name: str) -> str:
    name = name.strip()
    if name.startswith('"') and name.endswith('"'):
        return name[1:-1]
    return name


def _normalize_base_url(
    value: Optional[str],
    default_base_url: str,
    source_path: Path,
    allowlist: tuple[str, ...],
) -> Optional[str]:
    candidate = (value or default_base_url).rstrip("/")
    try:
        return validate_base_url("base_url", candidate, allowlist)
    except ValueError as exc:
        logging.getLogger("kmi").warning("Skipping auth %s due to invalid base_url: %s", source_path, exc)
        return None


def _parse_toml(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, ValueError):
        return {}


def _providers_from_config(config: dict) -> dict[str, dict[str, str]]:
    providers: dict[str, dict[str, str]] = {}
    root = config.get("providers") if isinstance(config, dict) else None
    if isinstance(root, dict):
        for name, values in root.items():
            if isinstance(values, dict):
                providers[str(name)] = {str(k): str(v) for k, v in values.items() if v is not None}
    for section, values in config.items() if isinstance(config, dict) else []:
        if not isinstance(section, str) or not section.startswith("providers."):
            continue
        name = _normalize_name(section.split(".", 1)[1])
        if isinstance(values, dict):
            providers[name] = {str(k): str(v) for k, v in values.items() if v is not None}
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


def _extract_email_from_config(config: dict) -> Optional[str]:
    stack = [config]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue
        values = {k: str(v) for k, v in current.items() if isinstance(v, (str, int, float))}
        email = _extract_email_from_values(values)
        if email:
            return email
        for value in current.values():
            if isinstance(value, dict):
                stack.append(value)
    return None


def _extract_email_from_text(text: str) -> Optional[str]:
    match = _EMAIL_RE.search(text)
    if match:
        return match.group(0)
    return None


def _account_from_toml(path: Path, default_base_url: str, allowlist: tuple[str, ...]) -> Optional[Account]:
    config = _parse_toml(path)
    providers = _providers_from_config(config)
    selected = _select_provider(providers)
    if not selected:
        return None
    provider_name, values = selected
    api_key = values.get("api_key")
    if not api_key:
        return None
    base_url = _normalize_base_url(values.get("base_url"), default_base_url, path, allowlist)
    if not base_url:
        return None
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


def _account_from_env(path: Path, default_base_url: str, allowlist: tuple[str, ...]) -> Optional[Account]:
    data = dotenv_values(path)
    api_key = data.get("KMI_API_KEY")
    if not api_key:
        return None
    label = _normalize_label(str(data.get("KMI_KEY_LABEL") or path.stem))
    base_url = _normalize_base_url(data.get("KMI_UPSTREAM_BASE_URL"), default_base_url, path, allowlist)
    if not base_url:
        return None
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


def _account_from_json(path: Path, default_base_url: str, allowlist: tuple[str, ...]) -> Optional[Account]:
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
    base_url = _normalize_base_url(values.get("base_url"), default_base_url, path, allowlist)
    if not base_url:
        return None
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


def collect_auth_files(auths_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in sorted(auths_dir.iterdir()):
        if path.is_dir():
            candidates.extend(sorted([p for p in path.iterdir() if p.is_file()]))
        elif path.is_file():
            candidates.append(path)
    return candidates


def load_accounts_from_auths_dir(
    auths_dir: Path, default_base_url: str, allowlist: tuple[str, ...] = ()
) -> list[Account]:
    auths_dir = auths_dir.expanduser()
    if not auths_dir.exists():
        return []
    accounts: list[Account] = []
    for path in collect_auth_files(auths_dir):
        if path.suffix.lower() == ".env":
            account = _account_from_env(path, default_base_url, allowlist)
        elif path.suffix.lower() == ".toml":
            account = _account_from_toml(path, default_base_url, allowlist)
        elif path.suffix.lower() in {".json", ".bak"} or path.name.endswith(".json.bak"):
            account = _account_from_json(path, default_base_url, allowlist)
        else:
            account = None
        if account:
            accounts.append(account)
    return accounts


def load_current_account(config_path: Path, allowlist: tuple[str, ...] = ()) -> Optional[Account]:
    if not config_path.exists():
        return None
    config = _parse_toml(config_path)
    root = config if isinstance(config, dict) else {}
    default_model = root.get("default_model") if isinstance(root, dict) else None

    provider_name = None
    if default_model:
        models = root.get("models") if isinstance(root.get("models"), dict) else None
        model = models.get(default_model) if isinstance(models, dict) else None
        if isinstance(model, dict) and model.get("provider"):
            provider_name = _normalize_name(str(model.get("provider", "")))
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
    base_url = _normalize_base_url(base_url, base_url, config_path, allowlist)
    if not base_url:
        return None
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


def copy_account_config(source: str, dest: Path) -> bool:
    src = Path(source).expanduser()
    if not src.exists() or src.suffix.lower() != ".toml":
        return False
    dest = dest.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".tmp")
    tmp_path.write_text(src.read_text(errors="ignore"), encoding="utf-8")
    os.replace(tmp_path, dest)
    return True
