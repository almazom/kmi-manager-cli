from __future__ import annotations

import os
import typer

from kmi_manager_cli import __version__
from kmi_manager_cli.config import (
    DEFAULT_KMI_AUTHS_DIR,
    DEFAULT_KMI_PROXY_BASE_PATH,
    DEFAULT_KMI_PROXY_LISTEN,
    DEFAULT_KMI_STATE_DIR,
    DEFAULT_KMI_DRY_RUN,
    DEFAULT_KMI_WRITE_CONFIG,
    DEFAULT_KMI_ROTATE_ON_TIE,
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
from kmi_manager_cli.proxy import run_proxy
from kmi_manager_cli.rotation import rotate_manual
from kmi_manager_cli.state import load_state, save_state
from kmi_manager_cli.trace_tui import run_trace_tui
from kmi_manager_cli.ui import render_accounts_health_dashboard, render_health_dashboard, render_registry_table, render_rotation_dashboard

APP_HELP = (
    "KMI Manager CLI for rotation, proxy, and tracing.\n"
    f"Version: {__version__}\n"
    "Config defaults:\n"
    f"  KMI_AUTHS_DIR={DEFAULT_KMI_AUTHS_DIR}\n"
    f"  KMI_PROXY_LISTEN={DEFAULT_KMI_PROXY_LISTEN}\n"
    f"  KMI_PROXY_BASE_PATH={DEFAULT_KMI_PROXY_BASE_PATH}\n"
    f"  KMI_STATE_DIR={DEFAULT_KMI_STATE_DIR}\n"
    f"  KMI_DRY_RUN={DEFAULT_KMI_DRY_RUN}\n"
    f"  KMI_WRITE_CONFIG={DEFAULT_KMI_WRITE_CONFIG}\n"
    f"  KMI_ROTATE_ON_TIE={DEFAULT_KMI_ROTATE_ON_TIE}\n"
    "Config file: .env in current project (override with KMI_ENV_PATH)\n"
    "Notes:\n"
    "  Auto-rotation must comply with provider ToS.\n"
    "  Auto-rotation is opt-in; set KMI_AUTO_ROTATE_ALLOWED=1 to enable.\n"
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


def _render_status(config) -> None:
    _note_mode(config)
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    idx = max(0, min(state.active_index, len(registry.keys) - 1))
    active_label = registry.keys[idx].label if registry.keys else "none"
    typer.echo(f"Active key: {active_label}")
    typer.echo(f"Active index: {state.active_index} | Rotation index: {state.rotation_index} | Auto-rotate: {state.auto_rotate}")


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
def proxy() -> None:
    """Start the local proxy server."""
    config = _load_config_or_exit()
    _note_mode(config)
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    scheme = "https" if config.proxy_tls_terminated else "http"
    typer.echo(f"Starting proxy at {scheme}://{config.proxy_listen}{config.proxy_base_path}")
    if config.proxy_require_tls and not config.proxy_tls_terminated:
        typer.echo("Note: TLS termination required for remote access (set KMI_PROXY_TLS_TERMINATED=1).")
    try:
        run_proxy(config, registry, state)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)


@app.command()
def trace() -> None:
    """Show live trace view."""
    config = _load_config_or_exit()
    _note_mode(config)
    run_trace_tui(config)


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
def status() -> None:
    """Show current rotation status."""
    config = _load_config_or_exit()
    _render_status(config)
