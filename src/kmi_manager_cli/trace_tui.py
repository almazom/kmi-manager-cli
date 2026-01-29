from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table

from kmi_manager_cli.config import Config
from kmi_manager_cli.trace import compute_confidence, compute_distribution, load_trace_entries, trace_path


console = Console()


def _build_table(entries: list[dict], window: int) -> Table:
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
    table = Table(title=title, caption=f"keys: {distribution}" + (f" | {warning}" if warning else ""))
    table.add_column("ts_msk")
    table.add_column("req_id")
    table.add_column("key")
    table.add_column("endpoint")
    table.add_column("status")
    table.add_column("latency_ms")

    for entry in entries[-20:]:
        table.add_row(
            str(entry.get("ts_msk", "")),
            str(entry.get("request_id", ""))[:8],
            str(entry.get("key_label", "")),
            str(entry.get("endpoint", "")),
            str(entry.get("status", "")),
            str(entry.get("latency_ms", "")),
        )
    return table


def run_trace_tui(config: Config, window: int = 200, refresh_seconds: float = 1.0) -> None:
    path = trace_path(config)
    console.print(f"Tracing {path} (Ctrl+C to exit)")
    try:
        with Live(_build_table([], window), refresh_per_second=4, console=console) as live:
            while True:
                entries = load_trace_entries(Path(path), window=window)
                live.update(_build_table(entries, window))
                time.sleep(refresh_seconds)
    except KeyboardInterrupt:
        console.print("Trace stopped")
