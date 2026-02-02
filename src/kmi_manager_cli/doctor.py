from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import socket
from pathlib import Path
from typing import Iterable, Optional

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from kmi_manager_cli.auth_accounts import collect_auth_files
from kmi_manager_cli.config import Config
from kmi_manager_cli.health import fetch_usage
from kmi_manager_cli.keys import load_auths_dir
from kmi_manager_cli.logging import get_logger
from kmi_manager_cli.rotation import clear_blocked, is_blocked
from kmi_manager_cli.security import is_insecure_permissions
from kmi_manager_cli.state import load_state, save_state
from kmi_manager_cli.ui import get_console


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    details: str
    fix: str = ""


_STATUS_META = {
    "ok": ("✅", "green"),
    "warn": ("⚠️", "yellow"),
    "fail": ("❌", "red"),
    "info": ("ℹ️", "cyan"),
}


def _status_badge(status: str) -> tuple[str, str]:
    return _STATUS_META.get(status, ("•", "white"))


def _proxy_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _normalize_connect_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def _proxy_base_url(config: Config) -> str:
    host, port = config.proxy_listen.rsplit(":", 1)
    host = _normalize_connect_host(host)
    scheme = "https" if config.proxy_tls_terminated else "http"
    return f"{scheme}://{host}:{port}{config.proxy_base_path}"


def _format_age(seconds: float) -> str:
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    return f"{int(seconds // 3600)}h ago"


def _file_status(path: Path, label: str) -> DoctorCheck:
    if not path.exists():
        return DoctorCheck(label, "warn", "missing", "Run requests through proxy to create it.")
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = _format_age((datetime.now(timezone.utc) - mtime).total_seconds())
    size_kb = max(1, int(path.stat().st_size / 1024))
    return DoctorCheck(label, "ok", f"updated {age}, {size_kb}KB")


def _collect_insecure(paths: Iterable[Path]) -> list[str]:
    insecure: list[str] = []
    for path in paths:
        if path.exists() and is_insecure_permissions(path):
            insecure.append(str(path))
    return insecure


def _check_env(config: Config) -> DoctorCheck:
    if config.env_path:
        return DoctorCheck("Env file", "ok", str(config.env_path))
    return DoctorCheck("Env file", "info", "no .env found; using environment variables")


def _check_auths(config: Config) -> DoctorCheck:
    registry = load_auths_dir(config.auths_dir, config.upstream_base_url, config.upstream_allowlist)
    count = len(registry.keys)
    if count == 0:
        return DoctorCheck(
            "Auth keys",
            "fail",
            f"no keys found in {config.auths_dir.expanduser()}",
            "Add auth files in _auths/ or set KMI_AUTHS_DIR.",
        )
    labels = ", ".join(key.label for key in registry.keys[:4])
    more = "" if count <= 4 else f" (+{count - 4} more)"
    return DoctorCheck("Auth keys", "ok", f"{count} key(s): {labels}{more}")


def _check_proxy(config: Config) -> DoctorCheck:
    host, port = config.proxy_listen.rsplit(":", 1)
    connect_host = _normalize_connect_host(host)
    if connect_host not in {"127.0.0.1", "localhost", "::1"} and not config.proxy_allow_remote:
        return DoctorCheck(
            "Proxy bind",
            "fail",
            f"remote bind disabled ({config.proxy_listen})",
            "Set KMI_PROXY_ALLOW_REMOTE=1 or use 127.0.0.1.",
        )
    if connect_host not in {"127.0.0.1", "localhost", "::1"} and config.proxy_require_tls and not config.proxy_tls_terminated:
        return DoctorCheck(
            "Proxy TLS",
            "fail",
            "remote bind requires TLS termination",
            "Set KMI_PROXY_TLS_TERMINATED=1 behind TLS.",
        )
    if connect_host not in {"127.0.0.1", "localhost", "::1"} and not config.proxy_token:
        return DoctorCheck(
            "Proxy auth",
            "fail",
            "remote bind requires KMI_PROXY_TOKEN",
            "Set KMI_PROXY_TOKEN or use localhost.",
        )
    listening = _proxy_listening(connect_host, int(port))
    if listening:
        return DoctorCheck("Proxy", "ok", f"listening on {connect_host}:{port}")
    return DoctorCheck("Proxy", "warn", f"not running on {connect_host}:{port}", "Run: kmi proxy")


def _check_kimi_env(config: Config) -> DoctorCheck:
    expected = _proxy_base_url(config)
    actual = os.getenv("KIMI_BASE_URL", "")
    api_key = os.getenv("KIMI_API_KEY", "")
    if not actual:
        return DoctorCheck(
            "Kimi env",
            "warn",
            "KIMI_BASE_URL not set",
            f'export KIMI_BASE_URL="{expected}"',
        )
    if actual != expected:
        return DoctorCheck(
            "Kimi env",
            "warn",
            f"KIMI_BASE_URL mismatch: {actual}",
            f'export KIMI_BASE_URL="{expected}"',
        )
    if not api_key:
        return DoctorCheck("Kimi env", "warn", "KIMI_API_KEY not set", 'export KIMI_API_KEY="proxy"')
    return DoctorCheck("Kimi env", "ok", "KIMI_BASE_URL and KIMI_API_KEY set")


def _check_state(config: Config) -> DoctorCheck:
    state_path = config.state_dir.expanduser() / "state.json"
    if not state_path.exists():
        return DoctorCheck("State", "warn", f"missing {state_path}", "Run any kmi command to create it.")
    try:
        data = json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return DoctorCheck("State", "fail", "state.json is corrupt", "Move/rename state.json and retry.")
    auto_rotate = bool(data.get("auto_rotate", False))
    return DoctorCheck("State", "info", f"auto_rotate={'on' if auto_rotate else 'off'}")


def _check_permissions(config: Config) -> DoctorCheck:
    auths_dir = config.auths_dir.expanduser()
    state_dir = config.state_dir.expanduser()
    trace_dir = state_dir / "trace"
    log_dir = state_dir / "logs"
    state_path = state_dir / "state.json"
    trace_path = trace_dir / "trace.jsonl"
    log_path = log_dir / "kmi.log"
    paths: list[Path] = []
    if auths_dir.exists():
        paths.append(auths_dir)
        paths.extend(collect_auth_files(auths_dir))
    if state_dir.exists():
        paths.append(state_dir)
    if trace_dir.exists():
        paths.append(trace_dir)
    if log_dir.exists():
        paths.append(log_dir)
    paths.extend([state_path, trace_path, log_path])
    insecure = _collect_insecure(paths)
    if not insecure:
        return DoctorCheck("Permissions", "ok", "no insecure paths detected")
    shown = ", ".join(insecure[:3])
    more = "" if len(insecure) <= 3 else f" (+{len(insecure) - 3} more)"
    return DoctorCheck(
        "Permissions",
        "warn",
        f"insecure: {shown}{more}",
        "Fix with chmod 700/600 or set KMI_ENFORCE_FILE_PERMS=1.",
    )


def collect_checks(config: Config) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = [
        _check_env(config),
        _check_auths(config),
        DoctorCheck("Dry run", "warn" if config.dry_run else "ok", "enabled" if config.dry_run else "disabled"),
        DoctorCheck(
            "Auto-rotate policy",
            "ok" if config.auto_rotate_allowed else "warn",
            "allowed" if config.auto_rotate_allowed else "disabled",
            "" if config.auto_rotate_allowed else "Set KMI_AUTO_ROTATE_ALLOWED=1.",
        ),
        _check_proxy(config),
        _check_kimi_env(config),
        _check_state(config),
        _file_status(config.state_dir.expanduser() / "trace" / "trace.jsonl", "Trace"),
        _file_status(config.state_dir.expanduser() / "logs" / "kmi.log", "Log"),
        _check_permissions(config),
    ]
    return checks


def _recheck_blocked_keys(config: Config, registry, state) -> tuple[int, int]:
    logger = get_logger(config)
    cleared = 0
    remaining = 0
    for key in registry.keys:
        if not is_blocked(state, key.label):
            continue
        usage = fetch_usage(
            config.upstream_base_url,
            key.api_key,
            dry_run=False,
            logger=logger,
            label=key.label,
        )
        if usage is not None:
            clear_blocked(state, key.label)
            cleared += 1
        else:
            remaining += 1
    return cleared, remaining


def run_doctor(config: Config, recheck_keys: bool = False, clear_blocklist: bool = False) -> int:
    console = get_console()
    checks = collect_checks(config)
    counts = {"ok": 0, "warn": 0, "fail": 0, "info": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1

    lines: list[Text] = []
    for check in checks:
        emoji, color = _status_badge(check.status)
        line = Text()
        line.append(f"{emoji} ", style=color)
        line.append(check.name, style="bold")
        line.append(": ")
        line.append(check.details)
        if check.fix:
            line.append("\n    fix: ", style="magenta")
            line.append(check.fix)
        lines.append(line)

    title = "KMI Doctor"
    panel = Panel(Group(*lines), title=title, border_style="blue")
    console.print(panel)
    summary = Text(
        f"OK={counts['ok']}  WARN={counts['warn']}  FAIL={counts['fail']}  INFO={counts['info']}",
        style="bold",
    )
    console.print(summary)
    if recheck_keys or clear_blocklist:
        registry = load_auths_dir(config.auths_dir, config.upstream_base_url, config.upstream_allowlist)
        state = load_state(config, registry)
        if clear_blocklist:
            cleared = clear_blocked(state)
            if cleared:
                save_state(config, state)
            console.print(f"Blocked keys cleared: {cleared}")
        else:
            if config.dry_run:
                console.print("Note: --recheck-keys uses live /usages calls even in dry-run.")
            cleared, remaining = _recheck_blocked_keys(config, registry, state)
            if cleared:
                save_state(config, state)
            console.print(f"Blocked keys rechecked: cleared={cleared}, still_blocked={remaining}")
    return 1 if counts["fail"] > 0 else 0
