# CLI Kimi Wrapper (force proxy env)

Source: `src/kmi_manager_cli/cli.py`

```python
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
```
