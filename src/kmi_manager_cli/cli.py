from __future__ import annotations

import typer

from kmi_manager_cli import __version__
from kmi_manager_cli.config import (
    DEFAULT_KMI_AUTHS_DIR,
    DEFAULT_KMI_PROXY_BASE_PATH,
    DEFAULT_KMI_PROXY_LISTEN,
    DEFAULT_KMI_STATE_DIR,
    DEFAULT_KMI_DRY_RUN,
    load_config,
)
from pathlib import Path

from kmi_manager_cli.auth_accounts import Account, load_accounts_from_auths_dir, load_current_account
from kmi_manager_cli.errors import no_keys_message, remediation_message
from kmi_manager_cli.health import get_accounts_health, get_health_map
from kmi_manager_cli.keys import Registry, load_auths_dir
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
    "Config file: .env (if present in working directory)\n"
    "Notes:\n"
    "  Auto-rotation must comply with provider ToS.\n"
    "  Remote proxy binding requires KMI_PROXY_ALLOW_REMOTE=1 and KMI_PROXY_TOKEN."
)

app = typer.Typer(add_completion=False, help=APP_HELP)
rotate_app = typer.Typer(help="Rotation commands")


def _ensure_single_mode(*flags: bool) -> None:
    if sum(1 for flag in flags if flag) > 1:
        raise typer.BadParameter("Choose only one mode: --rotate, --auto_rotate, --trace, --all, --health, or --status")


def _note_dry_run(config) -> None:
    if config.dry_run:
        typer.echo("NOTE: KMI_DRY_RUN=1 (dry-run enabled; upstream requests are simulated).")


def _load_registry_or_exit(config):
    registry = load_auths_dir(config.auths_dir, config.upstream_base_url)
    if not registry.keys:
        typer.echo(no_keys_message(config))
        raise typer.Exit(code=1)
    return registry


def _manual_rotate(config) -> None:
    _note_dry_run(config)
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    health = get_health_map(config, registry, state)
    try:
        active, rotated, reason = rotate_manual(registry, state, health=health, prefer_next_on_tie=config.dry_run)
    except RuntimeError:
        typer.echo(remediation_message())
        raise typer.Exit(code=1)
    save_state(config, state)
    render_rotation_dashboard(active.label, registry, state, health=health, rotated=rotated, reason=reason, dry_run=config.dry_run)


def _enable_auto_rotate(config) -> None:
    if not config.auto_rotate_allowed:
        typer.echo("Auto-rotation is disabled by policy (KMI_AUTO_ROTATE_ALLOWED=false).")
        raise typer.Exit(code=1)
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    state.auto_rotate = True
    save_state(config, state)
    typer.echo("Auto-rotation enabled (round-robin).")
    typer.echo("Reminder: ensure your provider allows key pooling/rotation per ToS.")


def _current_config_path() -> Path:
    return Path.home() / ".kimi" / "config.toml"


def _render_accounts_health(config) -> None:
    _note_dry_run(config)
    registry = load_auths_dir(config.auths_dir, config.upstream_base_url)
    state = load_state(config, registry)
    if registry.keys:
        idx = max(0, min(state.active_index, len(registry.keys) - 1))
        active_label = registry.keys[idx].label if registry.keys else "none"
        typer.echo(f"Active key: {active_label}")
    accounts = load_accounts_from_auths_dir(config.auths_dir, config.upstream_base_url)
    current = load_current_account(_current_config_path())
    if current:
        accounts = [current] + accounts
    if not accounts:
        typer.echo(no_keys_message(config))
        raise typer.Exit(code=1)
    health = get_accounts_health(config, accounts, state, force_real=True)
    render_accounts_health_dashboard(accounts, state, health, dry_run=config.dry_run)


def _render_current_health(config) -> None:
    _note_dry_run(config)
    registry = load_auths_dir(config.auths_dir, config.upstream_base_url)
    state = load_state(config, registry)
    if registry.keys:
        idx = max(0, min(state.active_index, len(registry.keys) - 1))
        active_label = registry.keys[idx].label if registry.keys else "none"
        typer.echo(f"Active key: {active_label}")
    current = load_current_account(_current_config_path())
    if not current:
        typer.echo("No current account found at ~/.kimi/config.toml")
        raise typer.Exit(code=1)
    # Try to map current to a known auth label without extra API calls.
    accounts = load_accounts_from_auths_dir(config.auths_dir, config.upstream_base_url)
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
    health = get_accounts_health(config, [current], state, force_real=True)
    render_accounts_health_dashboard([current], state, health, dry_run=config.dry_run)


def _render_status(config) -> None:
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
    health_flag: bool = typer.Option(False, "--health", help="Show health for current key only."),
    status_flag: bool = typer.Option(False, "--status", help="Show current rotation status."),
) -> None:
    if ctx.invoked_subcommand:
        return
    _ensure_single_mode(rotate, auto_rotate, trace, all_, health_flag, status_flag)

    if not any([rotate, auto_rotate, trace, all_, health_flag, status_flag]):
        typer.echo(ctx.get_help())
        raise typer.Exit()

    config = load_config()  # ensure env is loaded early
    if rotate:
        _manual_rotate(config)
        raise typer.Exit()
    if auto_rotate:
        _enable_auto_rotate(config)
        raise typer.Exit()
    if trace:
        run_trace_tui(config)
        raise typer.Exit()
    if all_:
        _render_accounts_health(config)
        raise typer.Exit()
    if health_flag:
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
    config = load_config()
    _note_dry_run(config)
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    typer.echo(f"Starting proxy at http://{config.proxy_listen}{config.proxy_base_path}")
    try:
        run_proxy(config, registry, state)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)


@app.command()
def trace() -> None:
    """Show live trace view."""
    config = load_config()
    _note_dry_run(config)
    run_trace_tui(config)


@rotate_app.callback(invoke_without_command=True)
def rotate_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand:
        return
    config = load_config()
    _manual_rotate(config)


@rotate_app.command("auto")
def rotate_auto() -> None:
    """Enable auto-rotation."""
    config = load_config()
    _enable_auto_rotate(config)


@app.command()
def health() -> None:
    """Show health of all keys."""
    config = load_config()
    _render_accounts_health(config)


app.add_typer(rotate_app, name="rotate")


@app.command()
def status() -> None:
    """Show current rotation status."""
    config = load_config()
    _render_status(config)
