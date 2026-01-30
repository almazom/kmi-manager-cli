from __future__ import annotations

import time
from pathlib import Path

from rich.align import Align
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from kmi_manager_cli.config import Config
from kmi_manager_cli.trace import compute_confidence, compute_distribution, load_trace_entries, trace_path
from kmi_manager_cli.ui import get_console


def _format_ts(value: str) -> str:
    if not value:
        return ""
    # Handle common formats: "YYYY-MM-DD HH:MM:SS +TZ", ISO, or "HH:MM:SS"
    if "T" in value and len(value) >= 19:
        return value[11:19]
    if " " in value:
        parts = value.split()
        if len(parts) >= 2 and len(parts[1]) >= 8:
            return parts[1][:8]
    return value[:8]


def _build_view(entries: list[dict], window: int) -> Panel:
    confidence = compute_confidence(entries)
    counts, total = compute_distribution(entries)
    distribution = ", ".join(f"{label}:{count}" for label, count in sorted(counts.items()))
    if not distribution:
        distribution = "no data"
    warning = ""
    if total == 0:
        warning = "warming up"
    elif total < window:
        warning = f"warming up {total}/{window}"
    elif confidence < 95:
        warning = "WARNING confidence < 95%"
    title = f"KMI TRACE | window={window} | confidence={confidence}%"
    lines: list[str] = []
    for entry in reversed(entries[-20:]):
        ts_raw = str(entry.get("ts", entry.get("ts_msk", "")))
        ts_short = _format_ts(ts_raw)
        req_id = str(entry.get("request_id", ""))[:6]
        method = str(entry.get("method", ""))[:1].upper()
        key = str(entry.get("key_label", ""))
        endpoint = str(entry.get("endpoint", ""))
        status = str(entry.get("status", ""))
        hint = str(entry.get("prompt_hint", "")).strip()
        line = f"{ts_short} | {req_id} | {method} | {key} | {endpoint} | {status}"
        if hint:
            line = f"{line} | {hint}"
        lines.append(line)

    body = Text("\n".join(lines) if lines else "no entries")
    footer = f"keys: {distribution}" + (f" | {warning}" if warning else "")
    group = Group(body, Align.left(Text(footer)))
    return Panel(group, title=title, expand=True)


def run_trace_tui(config: Config, window: int = 200, refresh_seconds: float = 1.0) -> None:
    console = get_console()
    path = trace_path(config)
    if config.dry_run:
        console.print("DRY RUN: upstream requests are simulated.")
    console.print(f"Tracing {path} (Ctrl+C to exit)")
    try:
        with Live(_build_view([], window), refresh_per_second=4, console=console) as live:
            while True:
                entries = load_trace_entries(Path(path), window=window)
                live.update(_build_view(entries, window))
                time.sleep(refresh_seconds)
    except KeyboardInterrupt:
        console.print("Trace stopped")
