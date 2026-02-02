from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar

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


class HighlightTracker:
    """Tracks newly appeared entries and their highlight duration."""
    
    HIGHLIGHT_SECONDS: ClassVar[float] = 5.0
    
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._highlighted_id: str | None = None
        self._highlight_until: float = 0.0
    
    def update(self, entries: list[dict]) -> str | None:
        """Update tracker with new entries and return the ID to highlight."""
        current_time = time.time()
        
        # Collect IDs from current entries (most recent first in reversed order)
        current_ids = {str(e.get("request_id", "")) for e in entries if e.get("request_id")}
        
        # Find new IDs that we haven't seen before
        new_ids = current_ids - self._seen_ids
        
        # If there are new entries, highlight the most recent one
        if new_ids and entries:
            # Get the most recent entry (last in the list since we display reversed)
            most_recent = entries[-1]
            new_id = str(most_recent.get("request_id", ""))
            if new_id in new_ids:
                self._highlighted_id = new_id
                self._highlight_until = current_time + self.HIGHLIGHT_SECONDS
        
        # Clear highlight if expired
        if current_time > self._highlight_until:
            self._highlighted_id = None
        
        # Update seen IDs
        self._seen_ids = current_ids
        
        return self._highlighted_id


def _build_view(
    entries: list[dict], 
    window: int, 
    highlight_id: str | None = None
) -> Panel:
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
    
    # Build lines as Text objects to support styling
    text_lines: list[Text] = []
    for entry in reversed(entries[-20:]):
        ts_raw = str(entry.get("ts", entry.get("ts_msk", "")))
        ts_short = _format_ts(ts_raw)
        req_id = str(entry.get("request_id", ""))[:6]
        method = str(entry.get("method", ""))[:1].upper()
        key = str(entry.get("key_label", ""))
        endpoint = str(entry.get("endpoint", ""))
        status = str(entry.get("status", ""))
        head = str(entry.get("prompt_head", "")).strip()
        hint = str(entry.get("prompt_hint", "")).strip()
        line = f"{ts_short} | {req_id} | {method} | {key} | {endpoint} | {status}"
        hint_tail = hint
        if head and hint and hint.lower().startswith(head.lower()):
            hint_tail = hint[len(head) :].lstrip()
        if head:
            line = f"{line} | {head}"
        if hint_tail:
            line = f"{line} | {hint_tail}"
        
        # Apply green color if this is the highlighted entry
        entry_id = str(entry.get("request_id", ""))
        if entry_id == highlight_id:
            text_lines.append(Text(line, style="green"))
        else:
            text_lines.append(Text(line))
    
    if text_lines:
        body = Text("\n").join(text_lines)
    else:
        body = Text("no entries")
    
    footer = f"keys: {distribution}" + (f" | {warning}" if warning else "")
    group = Group(body, Align.left(Text(footer)))
    return Panel(group, title=title, expand=True)


def run_trace_tui(config: Config, window: int = 200, refresh_seconds: float = 1.0) -> None:
    console = get_console()
    path = trace_path(config)
    if config.dry_run:
        console.print("DRY RUN: upstream requests are simulated.")
    console.print(f"Tracing {path} (Ctrl+C to exit)")
    
    tracker = HighlightTracker()
    
    try:
        with Live(_build_view([], window), refresh_per_second=4, console=console) as live:
            while True:
                entries = load_trace_entries(Path(path), window=window)
                highlight_id = tracker.update(entries)
                live.update(_build_view(entries, window, highlight_id))
                time.sleep(refresh_seconds)
    except KeyboardInterrupt:
        console.print("Trace stopped")
