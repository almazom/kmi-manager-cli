# CLI Proxy Control (auto‑kill + start/stop/restart)

Source: `src/kmi_manager_cli/cli.py`

```python
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
def proxy() -> None:
    """Start the local proxy server."""
    config = _load_config_or_exit()
    _note_mode(config)
    _ensure_proxy_port_free(config)
    registry = _load_registry_or_exit(config)
    state = load_state(config, registry)
    scheme = "https" if config.proxy_tls_terminated else "http"
    typer.echo(f"🚀 Starting proxy at {scheme}://{config.proxy_listen}{config.proxy_base_path}")
    if config.proxy_require_tls and not config.proxy_tls_terminated:
        typer.echo("Note: TLS termination required for remote access (set KMI_PROXY_TLS_TERMINATED=1).")
    try:
        run_proxy(config, registry, state)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)


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
```
