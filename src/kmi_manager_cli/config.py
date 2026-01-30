from __future__ import annotations

import os
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

DEFAULT_KMI_AUTHS_DIR = "_auths"
DEFAULT_KMI_PROXY_LISTEN = "127.0.0.1:54123"
DEFAULT_KMI_PROXY_BASE_PATH = "/kmi-rotor/v1"
DEFAULT_KMI_UPSTREAM_BASE_URL = "https://api.kimi.com/coding/v1"
DEFAULT_KMI_STATE_DIR = "~/.kmi"
DEFAULT_KMI_DRY_RUN = True
DEFAULT_KMI_AUTO_ROTATE_ALLOWED = False
DEFAULT_KMI_ROTATION_COOLDOWN_SECONDS = 300
DEFAULT_KMI_PROXY_ALLOW_REMOTE = False
DEFAULT_KMI_PROXY_TOKEN = ""
DEFAULT_KMI_PROXY_REQUIRE_TLS = True
DEFAULT_KMI_PROXY_TLS_TERMINATED = False
DEFAULT_KMI_PROXY_MAX_RPS = 0
DEFAULT_KMI_PROXY_MAX_RPM = 0
DEFAULT_KMI_PROXY_RETRY_MAX = 0
DEFAULT_KMI_PROXY_RETRY_BASE_MS = 250
DEFAULT_KMI_TRACE_MAX_MB = 5
DEFAULT_KMI_TRACE_BACKUPS = 3
DEFAULT_KMI_LOG_MAX_MB = 5
DEFAULT_KMI_LOG_BACKUPS = 3
DEFAULT_KMI_WRITE_CONFIG = True
DEFAULT_KMI_ROTATE_ON_TIE = True
DEFAULT_KMI_UPSTREAM_ALLOWLIST = ""


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    value = value.strip().lower()
    return value in {"1", "true", "yes", "on"}


def _require_non_empty(name: str, value: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _normalize_base_path(value: str) -> str:
    value = _require_non_empty("KMI_PROXY_BASE_PATH", value)
    if not value.startswith("/"):
        raise ValueError("KMI_PROXY_BASE_PATH must start with '/'")
    return value.rstrip("/") or "/"


def _parse_allowlist(value: Optional[str]) -> tuple[str, ...]:
    if not value:
        return ()
    items = [item.strip().lower() for item in value.split(",") if item.strip()]
    return tuple(items)


def _host_allowed(host: str, allowlist: tuple[str, ...]) -> bool:
    if not allowlist:
        return True
    host = host.lower()
    for entry in allowlist:
        if entry.startswith("*.") and host.endswith(entry[1:].lower()):
            return True
        if host == entry:
            return True
    return False


def validate_base_url(name: str, value: str, allowlist: tuple[str, ...]) -> str:
    value = _require_non_empty(name, value).strip()
    parsed = urlparse(value)
    if parsed.scheme.lower() != "https":
        raise ValueError(f"{name} must use https://")
    if not parsed.netloc:
        raise ValueError(f"{name} must include a host")
    host = parsed.hostname or ""
    if not _host_allowed(host, allowlist):
        raise ValueError(f"{name} host '{host}' is not in KMI_UPSTREAM_ALLOWLIST")
    return value.rstrip("/")


def _resolve_env_path() -> Optional[Path]:
    override = os.getenv("KMI_ENV_PATH")
    if override:
        return Path(override).expanduser()
    candidate = Path(".env")
    return candidate if candidate.exists() else None


@dataclass(frozen=True)
class Config:
    auths_dir: Path
    proxy_listen: str
    proxy_base_path: str
    upstream_base_url: str
    state_dir: Path
    dry_run: bool
    auto_rotate_allowed: bool
    rotation_cooldown_seconds: int
    proxy_allow_remote: bool
    proxy_token: str
    proxy_max_rps: int
    proxy_max_rpm: int
    proxy_retry_max: int
    proxy_retry_base_ms: int
    env_path: Optional[Path] = None
    trace_max_bytes: int = DEFAULT_KMI_TRACE_MAX_MB * 1024 * 1024
    trace_max_backups: int = DEFAULT_KMI_TRACE_BACKUPS
    log_max_bytes: int = DEFAULT_KMI_LOG_MAX_MB * 1024 * 1024
    log_max_backups: int = DEFAULT_KMI_LOG_BACKUPS
    write_config: bool = DEFAULT_KMI_WRITE_CONFIG
    rotate_on_tie: bool = DEFAULT_KMI_ROTATE_ON_TIE
    upstream_allowlist: tuple[str, ...] = ()
    proxy_require_tls: bool = DEFAULT_KMI_PROXY_REQUIRE_TLS
    proxy_tls_terminated: bool = DEFAULT_KMI_PROXY_TLS_TERMINATED



def _resolve_auths_dir() -> Path:
    env_val = os.getenv("KMI_AUTHS_DIR")
    if env_val:
        return Path(env_val).expanduser()
    candidate = Path(DEFAULT_KMI_AUTHS_DIR).expanduser()
    if candidate.exists():
        return candidate
    home_candidate = Path("~/.kimi/_auths").expanduser()
    if home_candidate.exists():
        return home_candidate
    return candidate


def load_config(env_path: Optional[Path] = None) -> Config:
    if env_path is None:
        env_path = _resolve_env_path()
    if env_path is not None:
        load_dotenv(env_path)
    else:
        load_dotenv()

    auths_dir = _resolve_auths_dir()
    proxy_listen = _require_non_empty("KMI_PROXY_LISTEN", os.getenv("KMI_PROXY_LISTEN", DEFAULT_KMI_PROXY_LISTEN))
    proxy_base_path = _normalize_base_path(os.getenv("KMI_PROXY_BASE_PATH", DEFAULT_KMI_PROXY_BASE_PATH))
    upstream_allowlist = _parse_allowlist(os.getenv("KMI_UPSTREAM_ALLOWLIST", DEFAULT_KMI_UPSTREAM_ALLOWLIST))
    upstream_base_url = validate_base_url(
        "KMI_UPSTREAM_BASE_URL",
        os.getenv("KMI_UPSTREAM_BASE_URL", DEFAULT_KMI_UPSTREAM_BASE_URL),
        upstream_allowlist,
    )
    state_dir = Path(os.getenv("KMI_STATE_DIR", DEFAULT_KMI_STATE_DIR)).expanduser()
    dry_run = _parse_bool(os.getenv("KMI_DRY_RUN"), DEFAULT_KMI_DRY_RUN)
    auto_rotate_allowed = _parse_bool(os.getenv("KMI_AUTO_ROTATE_ALLOWED"), DEFAULT_KMI_AUTO_ROTATE_ALLOWED)
    cooldown = int(os.getenv("KMI_ROTATION_COOLDOWN_SECONDS", str(DEFAULT_KMI_ROTATION_COOLDOWN_SECONDS)))
    proxy_allow_remote = _parse_bool(os.getenv("KMI_PROXY_ALLOW_REMOTE"), DEFAULT_KMI_PROXY_ALLOW_REMOTE)
    proxy_token = os.getenv("KMI_PROXY_TOKEN", DEFAULT_KMI_PROXY_TOKEN)
    proxy_require_tls = _parse_bool(os.getenv("KMI_PROXY_REQUIRE_TLS"), DEFAULT_KMI_PROXY_REQUIRE_TLS)
    proxy_tls_terminated = _parse_bool(os.getenv("KMI_PROXY_TLS_TERMINATED"), DEFAULT_KMI_PROXY_TLS_TERMINATED)
    proxy_max_rps = int(os.getenv("KMI_PROXY_MAX_RPS", str(DEFAULT_KMI_PROXY_MAX_RPS)))
    proxy_max_rpm = int(os.getenv("KMI_PROXY_MAX_RPM", str(DEFAULT_KMI_PROXY_MAX_RPM)))
    proxy_retry_max = int(os.getenv("KMI_PROXY_RETRY_MAX", str(DEFAULT_KMI_PROXY_RETRY_MAX)))
    proxy_retry_base_ms = int(os.getenv("KMI_PROXY_RETRY_BASE_MS", str(DEFAULT_KMI_PROXY_RETRY_BASE_MS)))
    trace_max_mb = int(os.getenv("KMI_TRACE_MAX_MB", str(DEFAULT_KMI_TRACE_MAX_MB)))
    trace_max_backups = int(os.getenv("KMI_TRACE_BACKUPS", str(DEFAULT_KMI_TRACE_BACKUPS)))
    log_max_mb = int(os.getenv("KMI_LOG_MAX_MB", str(DEFAULT_KMI_LOG_MAX_MB)))
    log_max_backups = int(os.getenv("KMI_LOG_BACKUPS", str(DEFAULT_KMI_LOG_BACKUPS)))
    write_config = _parse_bool(os.getenv("KMI_WRITE_CONFIG"), DEFAULT_KMI_WRITE_CONFIG)
    rotate_on_tie = _parse_bool(os.getenv("KMI_ROTATE_ON_TIE"), DEFAULT_KMI_ROTATE_ON_TIE)

    return Config(
        auths_dir=auths_dir,
        proxy_listen=proxy_listen,
        proxy_base_path=proxy_base_path,
        upstream_base_url=upstream_base_url,
        upstream_allowlist=upstream_allowlist,
        state_dir=state_dir,
        dry_run=dry_run,
        auto_rotate_allowed=auto_rotate_allowed,
        rotation_cooldown_seconds=cooldown,
        proxy_allow_remote=proxy_allow_remote,
        proxy_token=proxy_token,
        proxy_max_rps=proxy_max_rps,
        proxy_max_rpm=proxy_max_rpm,
        proxy_retry_max=proxy_retry_max,
        proxy_retry_base_ms=proxy_retry_base_ms,
        env_path=env_path,
        trace_max_bytes=max(trace_max_mb, 0) * 1024 * 1024,
        trace_max_backups=max(trace_max_backups, 0),
        log_max_bytes=max(log_max_mb, 0) * 1024 * 1024,
        log_max_backups=max(log_max_backups, 0),
        write_config=write_config,
        rotate_on_tie=rotate_on_tie,
        proxy_require_tls=proxy_require_tls,
        proxy_tls_terminated=proxy_tls_terminated,
    )
