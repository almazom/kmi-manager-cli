from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import shutil
import signal
import typer
import httpx

from kmi_manager_cli import __version__
from kmi_manager_cli.config import (
    DEFAULT_KMI_AUTHS_DIR,
    DEFAULT_KMI_PROXY_BASE_PATH,
    DEFAULT_KMI_PROXY_LISTEN,
    DEFAULT_KMI_STATE_DIR,
    DEFAULT_KMI_DRY_RUN,
    DEFAULT_KMI_WRITE_CONFIG,
    DEFAULT_KMI_ROTATE_ON_TIE,
    DEFAULT_KMI_PAYMENT_BLOCK_SECONDS,
    Config,
    load_config,
)
from pathlib import Path

from kmi_manager_cli.audit import log_audit_event
from kmi_manager_cli.auth_accounts import (
    Account,
    copy_account_config,
    load_accounts_from_auths_dir,
    load_current_account,
)
from kmi_manager_cli.errors import no_keys_message, remediation_message
from kmi_manager_cli.health import get_accounts_health, get_health_map
from kmi_manager_cli.keys import Registry, load_auths_dir
from kmi_manager_cli.logging import get_logger
from kmi_manager_cli.proxy import parse_listen, run_proxy
from kmi_manager_cli.rotation import is_blocked, is_exhausted, rotate_manual
from kmi_manager_cli.state import load_state, save_state
from kmi_manager_cli.trace import compute_confidence, compute_distribution, trace_path
from kmi_manager_cli.trace_tui import run_trace_tui
from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from kmi_manager_cli.ui import (
    get_console,
    render_accounts_health_dashboard,
    render_health_dashboard,
    render_registry_table,
    render_rotation_dashboard,
)
from kmi_manager_cli.doctor import run_doctor

DEFAULT_E2E_REQUESTS = 50
DEFAULT_E2E_BATCH = 10
DEFAULT_E2E_WINDOW = 50
DEFAULT_E2E_ENDPOINT = "/models"
DEFAULT_E2E_MIN_CONFIDENCE = 95.0
DEFAULT_E2E_TIMEOUT = 10.0
DEFAULT_E2E_PAUSE = 0.5
DEFAULT_E2E_SCHEME = "http"


APP_HELP = (
    "KMI Manager CLI for rotation, proxy, and tracing.\n"
    f"Version: {__version__}\n"
    "Config defaults:\n"
    f"  KMI_AUTHS_DIR={DEFAULT_KMI_AUTHS_DIR}\n"
    f"  KMI_PROXY_LISTEN={DEFAULT_KMI_PROXY_LISTEN}\n"
    f"  KMI_PROXY_BASE_PATH={DEFAULT_KMI_PROXY_BASE_PATH}\n"
    f"  KMI_STATE_DIR={DEFAULT_KMI_STATE_DIR}\n"
    f"  KMI_DRY_RUN={DEFAULT_KMI_DRY_RUN}\n"
    "  KMI_AUTO_ROTATE_E2E=1\n"
    f"  KMI_PAYMENT_BLOCK_SECONDS={DEFAULT_KMI_PAYMENT_BLOCK_SECONDS}\n"
    "  KMI_REQUIRE_USAGE_BEFORE_REQUEST=0\n"
    "  KMI_USAGE_CACHE_SECONDS=600\n"
    "  KMI_BLOCKLIST_RECHECK_SECONDS=3600\n"
    "  KMI_BLOCKLIST_RECHECK_MAX=3\n"
    "  KMI_FAIL_OPEN_ON_EMPTY_CACHE=1\n"
    f"  KMI_WRITE_CONFIG={DEFAULT_KMI_WRITE_CONFIG}\n"
    f"  KMI_ROTATE_ON_TIE={DEFAULT_KMI_ROTATE_ON_TIE}\n"
    "\n"
    "Config file: .env (override with KMI_ENV_PATH)\n"
    "\n"
    "Notes:\n"
    "  Auto-rotation must comply with provider ToS.\n"
    "  Auto-rotation is opt-in; set KMI_AUTO_ROTATE_ALLOWED=1 to enable.\n"
    "  Auto-rotation runs E2E by default; set KMI_AUTO_ROTATE_E2E=0 to skip.\n"
    "  Remote proxy binding requires KMI_PROXY_ALLOW_REMOTE=1 and KMI_PROXY_TOKEN.\n"
    "  For non-local binding, set KMI_PROXY_TLS_TERMINATED=1 (or KMI_PROXY_REQUIRE_TLS=0)."
)

app = typer.Typer(add_completion=False, help=APP_HELP)
rotate_app = typer.Typer(help="Rotation commands")


def _ensure_single_mode(*flags: bool) -> None:
    if sum(1 for flag in flags if flag) > 1:
        raise typer.BadParameter(
            "Choose only one mode: --rotate, --auto_rotate, --trace, --all, --health, --current, or --status"
        )


def _apply_output_flags(plain: bool, no_color: bool) -> None:
    if plain:
        os.environ["KMI_PLAIN"] = "1"
    if no_color:
        os.environ["KMI_NO_COLOR"] = "1"
        os.environ["NO_COLOR"] = "1"


def _note_mode(config) -> None:
    if config.dry_run:
        typer.echo("MODE: DRY-RUN (upstream requests are simulated).")
    else:
        typer.echo("MODE: LIVE (upstream requests enabled).")


def _load_config_or_exit() -> Config:
    try:
        return load_config()
    except ValueError as exc:
        typer.echo(f"Config error: {exc}")
        typer.echo("Hint: check .env or KMI_* environment variables.")
        raise typer.Exit(code=2)


def _load_registry_or_exit(config):
    logger = get_logger(config)
    registry = load_auths_dir(
        config.auths_dir,
        config.upstream_base_url,
        config.upstream_allowlist,
        logger=logger,
    )
    if not registry.keys:
        typer.echo(no_keys_message(config))
        raise typer.Exit(code=1)
    return registry


def _manual_rotate(config) -> None:
    _note_mode(config)
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    idx = max(0, min(state.active_index, len(registry.keys) - 1))
    previous_label = registry.keys[idx].label if registry.keys else "none"
    health = get_health_map(config, registry, state)
    try:
        active, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=config.rotate_on_tie)
    except RuntimeError:
        typer.echo(remediation_message())
        raise typer.Exit(code=1)
    save_state(config, state)
    if rotated and config.write_config and not config.dry_run:
        accounts = load_accounts_from_auths_dir(
            config.auths_dir,
            config.upstream_base_url,
            config.upstream_allowlist,
        )
        account_map = {account.label: account for account in accounts}
        selected = account_map.get(active.label)
        if selected and copy_account_config(selected.source, _current_config_path()):
            typer.echo(f"Updated ~/.kimi/config.toml from {Path(selected.source).name}")
            log_audit_event(
                get_logger(config),
                "config_written",
                source=selected.source,
                dest=str(_current_config_path()),
            )
        else:
            typer.echo("Warning: rotate config requires a .toml auth file; rotation state updated only.")
    render_rotation_dashboard(
        active.label,
        registry,
        state,
        health=health,
        rotated=rotated,
        reason=reason,
        dry_run=config.dry_run,
        previous_label=previous_label,
        time_zone=config.time_zone,
    )


def _enable_auto_rotate(config) -> None:
    if not config.auto_rotate_allowed:
        typer.echo("Auto-rotation is disabled by policy (KMI_AUTO_ROTATE_ALLOWED=false).")
        raise typer.Exit(code=1)
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    state.auto_rotate = True
    save_state(config, state)
    log_audit_event(get_logger(config), "auto_rotate_enabled")
    typer.echo("Auto-rotation enabled (round-robin).")
    typer.echo("Reminder: ensure your provider allows key pooling/rotation per ToS.")


def _disable_auto_rotate(config) -> None:
    registry = load_auths_dir(
        config.auths_dir,
        config.upstream_base_url,
        config.upstream_allowlist,
        logger=get_logger(config),
    )
    state = load_state(config, registry)
    if not state.auto_rotate:
        typer.echo("Auto-rotation is already disabled.")
        return
    state.auto_rotate = False
    save_state(config, state)
    log_audit_event(get_logger(config), "auto_rotate_disabled")
    typer.echo("Auto-rotation disabled.")


def _current_config_path() -> Path:
    return Path.home() / ".kimi" / "config.toml"


def _render_accounts_health(config) -> None:
    _note_mode(config)
    registry = load_auths_dir(
        config.auths_dir,
        config.upstream_base_url,
        config.upstream_allowlist,
        logger=get_logger(config),
    )
    state = load_state(config, registry)
    if registry.keys:
        idx = max(0, min(state.active_index, len(registry.keys) - 1))
        active_label = registry.keys[idx].label if registry.keys else "none"
        typer.echo(f"Active key: {active_label}")
    accounts = load_accounts_from_auths_dir(
        config.auths_dir,
        config.upstream_base_url,
        config.upstream_allowlist,
    )
    current = load_current_account(_current_config_path(), config.upstream_allowlist)
    if current:
        accounts = [current] + accounts
    if not accounts:
        typer.echo(no_keys_message(config))
        raise typer.Exit(code=1)
    health = get_accounts_health(config, accounts, state, force_real=False)
    render_accounts_health_dashboard(accounts, state, health, dry_run=config.dry_run, time_zone=config.time_zone)


def _render_current_health(config) -> None:
    _note_mode(config)
    registry = load_auths_dir(
        config.auths_dir,
        config.upstream_base_url,
        config.upstream_allowlist,
        logger=get_logger(config),
    )
    state = load_state(config, registry)
    if registry.keys:
        idx = max(0, min(state.active_index, len(registry.keys) - 1))
        active_label = registry.keys[idx].label if registry.keys else "none"
        typer.echo(f"Active key: {active_label}")
    current = load_current_account(_current_config_path(), config.upstream_allowlist)
    if not current:
        typer.echo("No current account found at ~/.kimi/config.toml")
        raise typer.Exit(code=1)
    # Try to map current to a known auth label without extra API calls.
    accounts = load_accounts_from_auths_dir(
        config.auths_dir,
        config.upstream_base_url,
        config.upstream_allowlist,
    )
    for account in accounts:
        if account.base_url == current.base_url and account.api_key == current.api_key:
            current = Account(
                id=current.id,
                label=f"current:{account.label}",
                api_key=current.api_key,
                base_url=current.base_url,
                source=current.source,
                email=current.email,
            )
            break
    health = get_accounts_health(config, [current], state, force_real=False)
    render_accounts_health_dashboard([current], state, health, dry_run=config.dry_run, time_zone=config.time_zone)


def _build_status_payload(config, registry, state) -> dict:
    idx = max(0, min(state.active_index, len(registry.keys) - 1))
    active_label = registry.keys[idx].label if registry.keys else "none"
    total_keys = len(registry.keys)
    disabled = sum(1 for key in registry.keys if key.disabled)
    blocked = sum(1 for key in registry.keys if is_blocked(state, key.label))
    exhausted = sum(1 for key in registry.keys if is_exhausted(state, key.label))

    host, port = parse_listen(config.proxy_listen)
    connect_host = _normalize_connect_host(host)
    listening = _proxy_listening(connect_host, port)
    pids = _find_listening_pids(port) if listening else None

    return {
        "mode": "dry-run" if config.dry_run else "live",
        "proxy": {
            "running": listening,
            "host": connect_host,
            "port": port,
            "url": _proxy_base_url(config),
            "pids": pids,
            "daemon_log": str(_proxy_daemon_log_path(config)),
        },
        "upstream": config.upstream_base_url,
        "keys": {
            "total": total_keys,
            "disabled": disabled,
            "blocked": blocked,
            "exhausted": exhausted,
        },
        "active_key": active_label,
        "rotation": {
            "active_index": state.active_index,
            "rotation_index": state.rotation_index,
            "auto_rotate": state.auto_rotate,
        },
        "policy": {
            "strict_usage_check": config.require_usage_before_request,
            "fail_open_on_empty_cache": config.fail_open_on_empty_cache,
        },
        "cache": {
            "usage_refresh_seconds": config.usage_cache_seconds,
            "blocklist_recheck_seconds": config.blocklist_recheck_seconds,
            "blocklist_max": config.blocklist_recheck_max,
        },
        "payment_block_seconds": config.payment_block_seconds,
        "last_health_refresh": state.last_health_refresh,
    }


def _status_badge(ok: bool, warn: bool = False) -> tuple[str, str]:
    if ok:
        return "🟢", "green"
    if warn:
        return "🟧", "yellow"
    return "🔴", "red"


def _render_status(config, *, as_json: bool = False) -> None:
    if not as_json:
        _note_mode(config)
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    payload = _build_status_payload(config, registry, state)
    if as_json:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=True))
        return
    console = get_console()

    proxy = payload["proxy"]
    pids = proxy["pids"]
    if not proxy["running"]:
        pid_text = "n/a"
    elif pids is None:
        pid_text = "unknown (lsof missing)"
    elif not pids:
        pid_text = "unknown"
    else:
        pid_text = ", ".join(str(pid) for pid in pids)

    title = Text("=== KMI Status ===", style="bold")
    console.print(title)

    proxy_emoji, proxy_color = _status_badge(proxy["running"])
    proxy_lines = [
        Text.assemble(
            (f"{proxy_emoji} ", proxy_color),
            ("Status: ", "bold"),
            ("running" if proxy["running"] else "stopped", proxy_color),
            (f" on {proxy['host']}:{proxy['port']} (pid: {pid_text})", ""),
        ),
        Text.assemble(("🔗 Proxy URL: ", "cyan"), (proxy["url"], "")),
        Text.assemble(("🌐 Upstream: ", "cyan"), (payload["upstream"], "")),
    ]
    console.print(Panel(Group(*proxy_lines), title="Proxy", border_style=proxy_color))
    console.print()

    keys = payload["keys"]
    keys_ok = keys["blocked"] == 0 and keys["exhausted"] == 0
    keys_warn = keys["disabled"] > 0
    keys_emoji, keys_color = _status_badge(keys_ok, warn=keys_warn)
    keys_lines = [
        Text.assemble(
            (f"{keys_emoji} ", keys_color),
            ("Keys: ", "bold"),
            ("total={total} disabled={disabled} blocked={blocked} exhausted={exhausted}".format(**keys), ""),
        ),
        Text.assemble(("🔑 Active key: ", "cyan"), (payload["active_key"], "")),
    ]
    console.print(Panel(Group(*keys_lines), title="Keys", border_style=keys_color))
    console.print()

    rotation = payload["rotation"]
    policy = payload["policy"]
    rotation_lines = [
        Text.assemble(
            ("🔁 Rotation: ", "cyan"),
            (
                f"active_index={rotation['active_index']} rotation_index={rotation['rotation_index']} "
                f"auto_rotate={rotation['auto_rotate']}",
                "",
            ),
        ),
        Text.assemble(
            ("🛡️ Policy: ", "cyan"),
            (
                "strict_usage_check="
                f"{'on' if policy['strict_usage_check'] else 'off'} "
                f"fail_open_on_empty_cache={'on' if policy['fail_open_on_empty_cache'] else 'off'}",
                "",
            ),
        ),
    ]
    console.print(Panel(Group(*rotation_lines), title="Rotation & Policy", border_style="blue"))
    console.print()

    cache = payload["cache"]
    last_refresh = payload["last_health_refresh"]
    refresh_ok = last_refresh is not None
    refresh_emoji, refresh_color = _status_badge(refresh_ok, warn=not refresh_ok)
    cache_lines = [
        Text.assemble(
            ("🧠 Cache: ", "cyan"),
            (
                "usage_refresh="
                f"{cache['usage_refresh_seconds']}s "
                f"blocklist_recheck={cache['blocklist_recheck_seconds']}s "
                f"blocklist_max={cache['blocklist_max']}",
                "",
            ),
        ),
        Text.assemble(("💳 Payment block: ", "cyan"), (f"{payload['payment_block_seconds']}s", "")),
        Text.assemble((f"{refresh_emoji} ", refresh_color), ("Health refresh: ", "bold"), (last_refresh or "never", "")),
    ]
    console.print(Panel(Group(*cache_lines), title="Cache & Health", border_style=refresh_color))
    console.print()

    log_line = Text.assemble(("🧾 Daemon log: ", "cyan"), (proxy["daemon_log"], ""))
    console.print(Panel(Group(log_line), title="Logs", border_style="blue"))

    alerts: list[Text] = []
    if not proxy["running"]:
        alerts.append(Text("Proxy is not running.", style="red"))
    if keys["blocked"] > 0:
        alerts.append(Text(f"{keys['blocked']} key(s) blocked (payment/auth).", style="red"))
    if keys["exhausted"] > 0:
        alerts.append(Text(f"{keys['exhausted']} key(s) exhausted (cooldown).", style="red"))
    if not refresh_ok:
        alerts.append(Text("No health refresh recorded yet.", style="yellow"))
    if alerts:
        console.print()
        console.print(Panel(Group(*alerts), title="Alerts", border_style="red"))


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    rotate: bool = typer.Option(False, "--rotate", help="Manually rotate to the most resourceful key."),
    auto_rotate: bool = typer.Option(
        False,
        "--auto_rotate",
        "--auto-rotate",
        help="Enable auto-rotation for proxy requests.",
    ),
    trace: bool = typer.Option(False, "--trace", help="Show live trace window."),
    all_: bool = typer.Option(False, "--all", help="Show health of all keys."),
    health_flag: bool = typer.Option(False, "--health", help="Show health for all keys."),
    current_flag: bool = typer.Option(False, "--current", help="Show health for current key only."),
    status_flag: bool = typer.Option(False, "--status", help="Show current rotation status."),
    plain: bool = typer.Option(False, "--plain", help="Disable rich formatting (plain text)."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colors (NO_COLOR)."),
) -> None:
    _apply_output_flags(plain, no_color)
    if ctx.invoked_subcommand:
        return
    _ensure_single_mode(rotate, auto_rotate, trace, all_, health_flag, current_flag, status_flag)

    if not any([rotate, auto_rotate, trace, all_, health_flag, current_flag, status_flag]):
        typer.echo(ctx.get_help())
        raise typer.Exit()

    config = _load_config_or_exit()  # ensure env is loaded early
    if rotate:
        _manual_rotate(config)
        raise typer.Exit()
    if auto_rotate:
        _enable_auto_rotate(config)
        if config.auto_rotate_e2e:
            _run_e2e(
                config,
                requests=DEFAULT_E2E_REQUESTS,
                batch=DEFAULT_E2E_BATCH,
                window=DEFAULT_E2E_WINDOW,
                endpoint=DEFAULT_E2E_ENDPOINT,
                min_confidence=DEFAULT_E2E_MIN_CONFIDENCE,
                timeout=DEFAULT_E2E_TIMEOUT,
                pause=DEFAULT_E2E_PAUSE,
                scheme=DEFAULT_E2E_SCHEME,
                enable_auto_rotate=False,
            )
        raise typer.Exit()
    if trace:
        run_trace_tui(config)
        raise typer.Exit()
    if health_flag or all_:
        _render_accounts_health(config)
        raise typer.Exit()
    if current_flag:
        _render_current_health(config)
        raise typer.Exit()
    if status_flag:
        _render_status(config)
        raise typer.Exit()


if __name__ == "__main__":
    app()


def main() -> None:
    app()


@app.command()
def proxy(
    daemon: bool = typer.Option(
        True,
        "--daemon/--foreground",
        help="Run in background (default) or keep in foreground.",
    ),
) -> None:
    """Start the local proxy server."""
    config = _load_config_or_exit()
    _note_mode(config)
    _ensure_proxy_port_free(config)
    scheme = "https" if config.proxy_tls_terminated else "http"
    typer.echo(f"🚀 Starting proxy at {scheme}://{config.proxy_listen}{config.proxy_base_path}")
    if config.proxy_require_tls and not config.proxy_tls_terminated:
        typer.echo("Note: TLS termination required for remote access (set KMI_PROXY_TLS_TERMINATED=1).")
    if daemon:
        _load_registry_or_exit(config)
        _start_proxy_daemon(config)
        if sys.stdin.isatty() and typer.confirm('Run "kmi trace" now?', default=False):
            run_trace_tui(config)
        raise typer.Exit()
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    try:
        run_proxy(config, registry, state)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    if sys.stdin.isatty() and typer.confirm('Run "kmi trace" now?', default=False):
        run_trace_tui(config)


@app.command("proxy-stop")
def proxy_stop(
    yes: bool = typer.Option(False, "--yes", "-y", help="Stop without confirmation."),
    force: bool = typer.Option(False, "--force", "-f", help="Force kill (SIGKILL)."),
) -> None:
    """Stop the proxy process listening on KMI_PROXY_LISTEN."""
    config = _load_config_or_exit()
    stopped = _stop_proxy(config, yes=yes, force=force)
    if not stopped:
        raise typer.Exit(code=1)


@app.command("proxy-logs")
def proxy_logs(
    follow: bool = typer.Option(True, "--follow/--no-follow", help="Follow logs (tail -f)."),
    lines: int = typer.Option(200, "--lines", "-n", help="Number of lines to show."),
    daemon: bool = typer.Option(True, "--daemon/--app", help="Show proxy daemon logs or app logs."),
    since: str = typer.Option("", "--since", help="Filter app logs since time (e.g. 10m, 1h, 2026-02-02T12:00:00Z)."),
    sleep_seconds: float = typer.Option(0.5, "--sleep", help="Follow poll interval in seconds."),
) -> None:
    """Tail proxy logs (daemon stdout/stderr or app logs)."""
    config = _load_config_or_exit()
    path = _proxy_daemon_log_path(config) if daemon else _app_log_path(config)
    since_dt = _parse_since(since)
    if since and since_dt is None:
        typer.echo("Invalid --since value. Use 10m/1h/30s or ISO timestamp (e.g. 2026-02-02T12:00:00Z).")
        raise typer.Exit(code=2)
    if daemon and since_dt is not None:
        typer.echo("Note: --since works only with --app logs; ignoring filter.")
        since_dt = None
    _tail_file(path, lines=lines, follow=follow, sleep_seconds=sleep_seconds, since=since_dt, json_lines=not daemon)


@app.command("proxy-restart")
def proxy_restart(
    yes: bool = typer.Option(True, "--yes", "-y", help="Stop without confirmation."),
    force: bool = typer.Option(False, "--force", "-f", help="Force kill (SIGKILL)."),
) -> None:
    """Restart the local proxy server."""
    config = _load_config_or_exit()
    _stop_proxy(config, yes=yes, force=force)
    proxy()


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
    host, port = parse_listen(config.proxy_listen)
    host = _normalize_connect_host(host)
    scheme = "https" if config.proxy_tls_terminated else "http"
    return f"{scheme}://{host}:{port}{config.proxy_base_path}"


def _proxy_daemon_log_path(config: Config) -> Path:
    log_dir = config.state_dir.expanduser() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "proxy.out"


def _app_log_path(config: Config) -> Path:
    log_dir = config.state_dir.expanduser() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "kmi.log"


def _read_tail_lines(path: Path, limit: int) -> list[str]:
    if limit <= 0 or not path.exists():
        return []
    buffer: list[str] = []
    from collections import deque

    tail = deque(maxlen=limit)
    with path.open("rb") as handle:
        for line in handle:
            tail.append(line.decode("utf-8", errors="ignore").rstrip("\n"))
    buffer.extend(tail)
    return buffer


def _parse_log_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    parsed = parse_iso_timestamp(value)
    if parsed:
        return parsed
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None


def _parse_since(value: str) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw[-1].lower() in {"s", "m", "h", "d"} and raw[:-1].isdigit():
        amount = int(raw[:-1])
        unit = raw[-1].lower()
        seconds = amount
        if unit == "m":
            seconds *= 60
        elif unit == "h":
            seconds *= 3600
        elif unit == "d":
            seconds *= 86400
        return datetime.now(timezone.utc) - timedelta(seconds=seconds)
    parsed = _parse_log_timestamp(raw)
    return parsed


def _filter_lines_since(lines: list[str], since: Optional[datetime], json_lines: bool) -> list[str]:
    if since is None:
        return lines
    filtered: list[str] = []
    for line in lines:
        ts_value = None
        if json_lines:
            try:
                payload = json.loads(line)
                ts_value = payload.get("ts")
            except Exception:
                ts_value = None
        else:
            ts_value = None
        if ts_value is None:
            continue
        parsed = _parse_log_timestamp(str(ts_value))
        if parsed is None:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed >= since:
            filtered.append(line)
    return filtered


def _tail_file(
    path: Path,
    lines: int,
    follow: bool,
    sleep_seconds: float,
    since: Optional[datetime],
    json_lines: bool,
) -> None:
    if not path.exists():
        typer.echo(f"Log file not found: {path}")
        raise typer.Exit(code=1)
    for line in _filter_lines_since(_read_tail_lines(path, lines), since, json_lines):
        typer.echo(line)
    if not follow:
        return
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        while True:
            data = handle.readline()
            if data:
                line = data.decode("utf-8", errors="ignore").rstrip("\n")
                if since is None:
                    typer.echo(line)
                else:
                    filtered = _filter_lines_since([line], since, json_lines)
                    if filtered:
                        typer.echo(filtered[0])
                continue
            time.sleep(max(sleep_seconds, 0.1))


def _start_proxy_daemon(config: Config) -> None:
    kmi_bin = shutil.which("kmi")
    if not kmi_bin:
        typer.echo("❌ 'kmi' executable not found in PATH; cannot start daemon.")
        raise typer.Exit(code=1)
    log_path = _proxy_daemon_log_path(config)
    handle = log_path.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        [kmi_bin, "proxy", "--foreground"],
        stdout=handle,
        stderr=handle,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    handle.close()
    typer.echo("✅ Proxy started in background (daemon).")
    typer.echo(f"PID: {proc.pid}")
    typer.echo(f"Logs: {log_path}")
    typer.echo("Stop: kmi proxy-stop")


def _ensure_proxy_port_free(config: Config) -> None:
    host, port = parse_listen(config.proxy_listen)
    connect_host = _normalize_connect_host(host)
    typer.echo(f"🩺 Doctor: checking {connect_host}:{port}")
    if not _proxy_listening(connect_host, port):
        typer.echo("✅ No existing listener detected.")
        return
    typer.echo(f"⚠️ Existing listener detected on {connect_host}:{port}")
    pids = _find_listening_pids(port)
    if pids is None:
        typer.echo("❌ 'lsof' not available; cannot auto-stop. Use Ctrl+C or kmi proxy-stop.")
        raise typer.Exit(code=1)
    typer.echo(f"🛑 Stopping PID(s): {', '.join(str(pid) for pid in pids)}")
    _terminate_pids(pids, force=False)
    time.sleep(0.5)
    if _proxy_listening(connect_host, port):
        typer.echo("⚠️ Still listening, forcing kill.")
        _terminate_pids(pids, force=True)
        time.sleep(0.5)
    if _proxy_listening(connect_host, port):
        typer.echo("❌ Port still in use. Stop manually and retry.")
        raise typer.Exit(code=1)
    typer.echo("✅ Old listener stopped.")


def _find_listening_pids(port: int) -> list[int] | None:
    lsof = shutil.which("lsof")
    if not lsof:
        return None
    result = subprocess.run(
        [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return sorted(set(pids))


def _terminate_pids(pids: list[int], force: bool) -> None:
    sig = signal.SIGKILL if force else signal.SIGTERM
    for pid in pids:
        os.kill(pid, sig)


def _stop_proxy(config: Config, *, yes: bool, force: bool) -> bool:
    host, port = parse_listen(config.proxy_listen)
    pids = _find_listening_pids(port)
    if pids is None:
        typer.echo("Unable to find proxy PID because 'lsof' is not available.")
        typer.echo("Stop it manually (Ctrl+C in the proxy terminal), or install lsof.")
        return False
    if not pids:
        typer.echo(f"No process is listening on {host}:{port}.")
        return False
    typer.echo(f"Found listener(s) on {host}:{port}: {', '.join(str(pid) for pid in pids)}")
    if not yes and not typer.confirm("Stop these process(es)?"):
        return False
    _terminate_pids(pids, force)
    typer.echo("Proxy stopped.")
    return True


def _read_new_trace_entries(path: Path, offset: int) -> tuple[list[dict], int]:
    if not path.exists():
        return [], offset
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
    if not data:
        return [], offset
    new_offset = offset + len(data)
    entries: list[dict] = []
    for line in data.splitlines():
        try:
            entries.append(json.loads(line.decode("utf-8", errors="ignore")))
        except json.JSONDecodeError:
            continue
    return entries, new_offset


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return ", ".join(f"{label}:{count}" for label, count in sorted(counts.items()))


def _run_e2e(
    config: Config,
    *,
    requests: int,
    batch: int,
    window: int,
    endpoint: str,
    min_confidence: float,
    timeout: float,
    pause: float,
    scheme: str,
    show_mode: bool = True,
    enable_auto_rotate: bool = True,
) -> float:
    if requests <= 0 or batch <= 0 or window <= 0:
        raise typer.BadParameter("--requests, --batch, and --window must be positive")
    scheme = scheme.lower()
    if scheme not in {"http", "https"}:
        raise typer.BadParameter("--scheme must be 'http' or 'https'")
    if show_mode:
        _note_mode(config)
    if not config.auto_rotate_allowed:
        typer.echo("Auto-rotation is disabled by policy (KMI_AUTO_ROTATE_ALLOWED=false).")
        raise typer.Exit(code=1)
    if enable_auto_rotate:
        _enable_auto_rotate(config)

    registry = _load_registry_or_exit(config)
    host, port = parse_listen(config.proxy_listen)
    connect_host = _normalize_connect_host(host)
    started_proc = None
    if not _proxy_listening(connect_host, port):
        typer.echo("Proxy is not running; starting it now...")
        try:
            started_proc = subprocess.Popen(["kmi", "proxy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            typer.echo("Unable to start proxy via 'kmi proxy'. Ensure 'kmi' is in PATH.")
            raise typer.Exit(code=1)
        for _ in range(20):
            time.sleep(0.5)
            if _proxy_listening(connect_host, port):
                break
    if not _proxy_listening(connect_host, port):
        typer.echo("Proxy did not start or is not reachable.")
        if started_proc:
            started_proc.terminate()
        raise typer.Exit(code=1)

    base = f"{scheme}://{connect_host}:{port}{config.proxy_base_path.rstrip('/')}"
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base}{path}"

    headers = {}
    if config.proxy_token:
        headers["Authorization"] = f"Bearer {config.proxy_token}"

    trace_file = trace_path(config)
    trace_file.parent.mkdir(parents=True, exist_ok=True)
    offset = trace_file.stat().st_size if trace_file.exists() else 0

    total_sent = 0
    errors = 0
    confidence = 0.0
    collected: list[dict] = []
    try:
        with httpx.Client(timeout=timeout) as client:
            while total_sent < requests:
                current_batch = min(batch, requests - total_sent)
                for _ in range(current_batch):
                    try:
                        resp = client.request("GET", url, headers=headers)
                        if resp.status_code >= 400:
                            errors += 1
                    except httpx.HTTPError:
                        errors += 1
                    total_sent += 1
                if pause > 0:
                    time.sleep(pause)
                new_entries, offset = _read_new_trace_entries(trace_file, offset)
                for entry in new_entries:
                    if entry.get("endpoint") == path:
                        collected.append(entry)
                sample = collected[-window:] if collected else []
                confidence = compute_confidence(sample) if sample else 0.0
                counts, _ = compute_distribution(sample)
                keys_seen = len(counts)
                typer.echo(
                    f"sent={total_sent}/{requests} trace={len(collected)} keys={keys_seen}/{len(registry.keys)} "
                    f"confidence={confidence}% errors={errors}"
                )
                if confidence >= min_confidence and len(sample) >= min(window, requests):
                    break
    finally:
        if started_proc:
            started_proc.terminate()
            try:
                started_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                started_proc.kill()

    sample = collected[-window:] if collected else []
    counts, total = compute_distribution(sample)
    typer.echo(f"Distribution (last {total}): {_format_counts(counts)}")
    if confidence >= min_confidence:
        typer.echo(f"E2E OK: confidence={confidence}%")
    else:
        typer.echo(f"E2E WARN: confidence={confidence}% < {min_confidence}%")
    return confidence


@app.command()
def e2e(
    requests: int = typer.Option(DEFAULT_E2E_REQUESTS, "--requests", "-n", help="Total requests to send."),
    batch: int = typer.Option(DEFAULT_E2E_BATCH, "--batch", help="Requests per batch."),
    window: int = typer.Option(DEFAULT_E2E_WINDOW, "--window", help="Window size for confidence."),
    endpoint: str = typer.Option(DEFAULT_E2E_ENDPOINT, "--endpoint", help="Endpoint path to hit via proxy."),
    min_confidence: float = typer.Option(DEFAULT_E2E_MIN_CONFIDENCE, "--min-confidence", help="Target confidence threshold."),
    timeout: float = typer.Option(DEFAULT_E2E_TIMEOUT, "--timeout", help="Per-request timeout (seconds)."),
    pause: float = typer.Option(DEFAULT_E2E_PAUSE, "--pause", help="Pause between batches (seconds)."),
    scheme: str = typer.Option(DEFAULT_E2E_SCHEME, "--scheme", help="Proxy scheme (http or https)."),
) -> None:
    """Run a round-robin proxy E2E check."""
    config = _load_config_or_exit()
    _run_e2e(
        config,
        requests=requests,
        batch=batch,
        window=window,
        endpoint=endpoint,
        min_confidence=min_confidence,
        timeout=timeout,
        pause=pause,
        scheme=scheme,
        enable_auto_rotate=True,
    )


@app.command()
def trace() -> None:
    """Show live trace view."""
    config = _load_config_or_exit()
    _note_mode(config)
    run_trace_tui(config)


@app.command()
def doctor(
    plain: bool = typer.Option(False, "--plain", help="Disable rich formatting (plain text)."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colors (NO_COLOR)."),
    recheck_keys: bool = typer.Option(
        False,
        "--recheck-keys",
        help="Recheck blocked keys via /usages and clear if healthy (live call).",
    ),
    clear_blocklist: bool = typer.Option(
        False,
        "--clear-blocklist",
        help="Clear blocked keys without checks.",
    ),
) -> None:
    """Run diagnostics and show a doctor report."""
    _apply_output_flags(plain, no_color)
    if recheck_keys and clear_blocklist:
        raise typer.BadParameter("Choose only one: --recheck-keys or --clear-blocklist.")
    config = _load_config_or_exit()
    exit_code = run_doctor(config, recheck_keys=recheck_keys, clear_blocklist=clear_blocklist)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command("kimi", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def kimi_proxy(ctx: typer.Context) -> None:
    """Run kimi CLI with proxy env injected."""
    config = _load_config_or_exit()
    kimi_bin = shutil.which("kimi")
    if not kimi_bin:
        typer.echo("kimi executable not found in PATH.")
        raise typer.Exit(code=1)
    if config.proxy_token:
        typer.echo("Warning: KMI_PROXY_TOKEN is set; kimi CLI does not send proxy auth headers.")
    env = os.environ.copy()
    env["KIMI_BASE_URL"] = _proxy_base_url(config)
    env["KIMI_API_KEY"] = "proxy"
    result = subprocess.run([kimi_bin, *ctx.args], env=env)
    raise typer.Exit(code=result.returncode)


@rotate_app.callback(invoke_without_command=True)
def rotate_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand:
        return
    config = _load_config_or_exit()
    _manual_rotate(config)


@rotate_app.command("auto")
def rotate_auto() -> None:
    """Enable auto-rotation."""
    config = _load_config_or_exit()
    _note_mode(config)
    _enable_auto_rotate(config)
    if config.auto_rotate_e2e:
        _run_e2e(
            config,
            requests=DEFAULT_E2E_REQUESTS,
            batch=DEFAULT_E2E_BATCH,
            window=DEFAULT_E2E_WINDOW,
            endpoint=DEFAULT_E2E_ENDPOINT,
            min_confidence=DEFAULT_E2E_MIN_CONFIDENCE,
            timeout=DEFAULT_E2E_TIMEOUT,
            pause=DEFAULT_E2E_PAUSE,
            scheme=DEFAULT_E2E_SCHEME,
            show_mode=False,
            enable_auto_rotate=False,
        )


@rotate_app.command("off")
def rotate_off() -> None:
    """Disable auto-rotation."""
    config = _load_config_or_exit()
    _note_mode(config)
    _disable_auto_rotate(config)


@app.command()
def health() -> None:
    """Show health of all keys."""
    config = _load_config_or_exit()
    _render_accounts_health(config)


app.add_typer(rotate_app, name="rotate")


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", help="Output status as JSON."),
) -> None:
    """Show current rotation status."""
    config = _load_config_or_exit()
    _render_status(config, as_json=json_output)
