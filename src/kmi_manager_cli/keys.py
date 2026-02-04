"""Key registry management and API key loading.

This module handles loading API keys from the auth directory (_auths/),
parsing .env files, and building a prioritized registry of available keys.

Key Components:
    KeyRecord: Immutable record of a single API key with metadata
    Registry: Container for all keys with active index tracking
    load_auths_dir: Scans auth directory and builds registry
    mask_key: Masks API keys for safe display/logging

Key Prioritization:
    Keys are sorted by:
    1. Priority (higher first, from KMI_KEY_PRIORITY)
    2. Label (alphabetically, case-insensitive)

Security:
    Key hashes (SHA-256) are computed for trace correlation without
    exposing actual key values.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from dotenv import dotenv_values

from kmi_manager_cli.auth_accounts import (
    collect_auth_files,
    load_accounts_from_auths_dir,
)
from kmi_manager_cli.config import DEFAULT_KMI_UPSTREAM_BASE_URL
from kmi_manager_cli.security import warn_if_insecure


"""Key registry management and API key loading.

This module handles loading API keys from the auth directory (_auths/),
parsing .env files, and building a prioritized registry of available keys.

Key Components:
    KeyRecord: Immutable record of a single API key with metadata
    Registry: Container for all keys with active index tracking
    load_auths_dir: Scans auth directory and builds registry
    mask_key: Masks API keys for safe display/logging

Key Prioritization:
    Keys are sorted by:
    1. Priority (higher first, from KMI_KEY_PRIORITY)
    2. Label (alphabetically, case-insensitive)

Duplicate Prevention:
    Duplicate API keys (by value) are deduplicated, keeping the first
    encountered instance.

Security:
    Key hashes (SHA-256) are computed for trace correlation without
    exposing actual key values.
"""


def _parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}***{api_key[-4:]}"


@dataclass(frozen=True)
class KeyRecord:
    label: str
    api_key: str
    priority: int = 0
    disabled: bool = False
    key_hash: str = field(init=False)

    def __post_init__(self) -> None:
        digest = hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()
        object.__setattr__(self, "key_hash", digest[:12])


@dataclass
class Registry:
    keys: list[KeyRecord]
    active_index: int = 0

    @property
    def active_key(self) -> Optional[KeyRecord]:
        if not self.keys:
            return None
        idx = max(0, min(self.active_index, len(self.keys) - 1))
        return self.keys[idx]

    def find_by_label(self, label: str) -> Optional[KeyRecord]:
        for key in self.keys:
            if key.label == label:
                return key
        return None


def load_env_file(path: Path) -> dict[str, str]:
    data = dotenv_values(path)
    return {k: v for k, v in data.items() if v is not None}


def load_auths_dir(
    auths_dir: Path,
    default_base_url: str = DEFAULT_KMI_UPSTREAM_BASE_URL,
    allowlist: tuple[str, ...] = (),
    logger=None,
) -> Registry:
    auths_dir = auths_dir.expanduser()
    if not auths_dir.exists():
        return Registry(keys=[], active_index=0)
    records: list[KeyRecord] = []

    env_meta: dict[str, tuple[int, bool]] = {}
    for path in collect_auth_files(auths_dir):
        if logger is not None:
            warn_if_insecure(path, logger, "auth_file")
        if path.suffix.lower() != ".env":
            continue
        data = load_env_file(path)
        priority_raw = data.get("KMI_KEY_PRIORITY", "0")
        try:
            priority = int(priority_raw)
        except ValueError:
            priority = 0
        disabled = _parse_bool(data.get("KMI_KEY_DISABLED"))
        env_meta[str(path)] = (priority, disabled)

    accounts = load_accounts_from_auths_dir(auths_dir, default_base_url, allowlist)
    seen_keys: set[str] = set()
    for account in accounts:
        if not account.api_key or account.api_key in seen_keys:
            continue
        priority, disabled = env_meta.get(account.source, (0, False))
        records.append(
            KeyRecord(
                label=account.label,
                api_key=account.api_key,
                priority=priority,
                disabled=disabled,
            )
        )
        seen_keys.add(account.api_key)

    records.sort(key=lambda r: (-r.priority, r.label.lower()))
    return Registry(keys=records, active_index=0)


def iter_masked_keys(records: Iterable[KeyRecord]) -> list[tuple[str, str]]:
    return [(record.label, mask_key(record.api_key)) for record in records]
