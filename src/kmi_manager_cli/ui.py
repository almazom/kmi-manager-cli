from __future__ import annotations

from datetime import datetime, timezone, timedelta
import os
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from kmi_manager_cli.auth_accounts import Account
from kmi_manager_cli.health import HealthInfo, LimitInfo
from kmi_manager_cli.keys import Registry, mask_key
from kmi_manager_cli.state import State


console = Console()


def render_registry_table(
    registry: Registry,
    state: Optional[State] = None,
    title: str = "KMI Keys",
    health: Optional[dict[str, HealthInfo]] = None,
) -> None:
    table = Table(title=title)
    table.add_column("Label", style="bold")
    table.add_column("Status")
    table.add_column("Last Used")
    table.add_column("Key")

    for key in registry.keys:
        key_state = state.keys.get(key.label) if state else None
        status = health.get(key.label).status if health and key.label in health else None
        if not status:
            status = "disabled" if key.disabled else "unknown"
        last_used = key_state.last_used if key_state and key_state.last_used else "-"
        table.add_row(key.label, status, last_used, mask_key(key.api_key))

    console.print(table)


def render_rotation_dashboard(
    active_label: str,
    registry: Registry,
    state: State,
    health: Optional[dict[str, HealthInfo]] = None,
    rotated: bool = True,
    reason: Optional[str] = None,
    dry_run: bool = False,
) -> None:
    if rotated:
        console.print("Rotation complete")
    else:
        console.print("Rotation skipped")
    if dry_run:
        console.print("DRY RUN: upstream requests are simulated.")
    if reason:
        console.print(f"Reason: {reason}")
    console.print(f"Active key: {active_label}")
    render_registry_table(registry, state, title="Key Dashboard", health=health)


def _status_meta(status: str) -> tuple[str, str, str, int]:
    status = status.lower()
    if status == "healthy":
        return "OK", "green", "🟢", 0
    if status == "warn":
        return "WARN", "orange3", "🟧", 1
    if status in {"blocked", "exhausted"}:
        return "EXHAUSTED", "red", "🔴", 2
    if status == "disabled":
        return "DISABLED", "red", "🔴", 2
    return "UNKNOWN", "dim", "⚪", 3


def _format_percent(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.0f}%"


def _format_used_limit(used: Optional[int], limit: Optional[int]) -> Optional[str]:
    if used is None or limit is None:
        return None
    return f"{used}/{limit}"


def _percent_used(used: Optional[int], limit: Optional[int], remaining: Optional[int] = None) -> Optional[float]:
    if used is None and limit is not None and remaining is not None:
        used = max(limit - remaining, 0)
    if used is None or limit is None or limit <= 0:
        return None
    return (used / limit) * 100


def _format_reset_hint(hint: Optional[str]) -> str:
    if not hint:
        return "-"
    raw = hint.strip()
    if raw.lower().startswith("resets in"):
        parts = raw.split()
        if len(parts) >= 3 and parts[2].rstrip("s").isdigit():
            seconds = int(parts[2].rstrip("s"))
        else:
            try:
                seconds = int(parts[-1].rstrip("s"))
            except Exception:
                return raw
        return _human_duration(seconds)
    try:
        ts = raw.replace("Z", "+00:00")
        when = datetime.fromisoformat(ts)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = int((when - datetime.now(timezone.utc)).total_seconds())
        return _human_duration(seconds)
    except Exception:
        return raw


def _human_duration(seconds: int) -> str:
    if seconds <= 0:
        return "now"
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    if days > 0:
        return f"{days}d {hours % 24}h"
    if hours > 0:
        return f"{hours}h {minutes % 60}m"
    return f"{minutes}m"


def _reset_seconds(hint: Optional[str]) -> Optional[int]:
    if not hint:
        return None
    raw = hint.strip()
    if raw.lower().startswith("resets in"):
        parts = raw.split()
        try:
            value = int(parts[-1].rstrip("s"))
        except Exception:
            return None
        return max(value, 0)
    try:
        ts = raw.replace("Z", "+00:00")
        when = datetime.fromisoformat(ts)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = int((when - datetime.now(timezone.utc)).total_seconds())
        return max(seconds, 0)
    except Exception:
        return None


def _msk_now() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")


def render_health_dashboard(registry: Registry, state: State, health: dict[str, HealthInfo], dry_run: bool = False) -> None:
    ok = warn = red = unknown = 0
    best_label = None
    best_remaining = -1.0
    if dry_run:
        console.print("DRY RUN: upstream requests are simulated.")

    rows = []
    for key in registry.keys:
        info = health.get(key.label)
        status = info.status if info else "unknown"
        label = key.label
        remaining = info.remaining_percent if info else None
        status_label, color, icon, group = _status_meta(status)
        if status == "healthy":
            ok += 1
        elif status == "warn":
            warn += 1
        elif status in {"blocked", "exhausted", "disabled"}:
            red += 1
        else:
            unknown += 1

        remaining_sort = remaining if remaining is not None else -1.0
        if status == "healthy" and remaining_sort > best_remaining:
            best_remaining = remaining_sort
            best_label = label

        rows.append(
            {
                "label": label,
                "status": status,
                "status_label": status_label,
                "color": color,
                "icon": icon,
                "group": group,
                "remaining": remaining,
                "used": info.used if info else None,
                "limit": info.limit if info else None,
                "reset": info.reset_hint if info else None,
                "error_rate": info.error_rate if info else 0.0,
                "last_used": state.keys.get(label).last_used if label in state.keys else None,
            }
        )

    rows.sort(key=lambda r: (r["group"], -(r["remaining"] if r["remaining"] is not None else -1.0), r["label"]))

    # Header panel removed per UX request.

    for row in rows:
        status_line = Text.assemble(
            ("Status ", "bold"),
            (f"{row['icon']} {row['status_label']}", row["color"]),
        )
        used_limit = _format_used_limit(row["used"], row["limit"])
        if used_limit:
            remaining_line = Text.assemble(
                ("Remaining ", "bold"),
                (_format_percent(row["remaining"]), row["color"]),
                (" | Used ", "bold"),
                (used_limit, "white"),
            )
        else:
            remaining_line = Text.assemble(
                ("Remaining ", "bold"),
                (_format_percent(row["remaining"]), row["color"]),
            )
        primary_reset = _format_reset_hint(row["reset"])
        primary_used_limit = _format_used_limit(row["used"], row["limit"])
        primary_summary_parts = []
        if primary_used_limit:
            primary_summary_parts.append(primary_used_limit)
        if primary_reset != "-":
            primary_summary_parts.append(f"resets {primary_reset}")
        primary_line = None
        if primary_summary_parts:
            primary_summary = " | ".join(primary_summary_parts)
            primary_line = Text.assemble(("Weekly balance ", "bold"), (primary_summary, "white"))
        last_used = row["last_used"]
        last_used_line = Text.assemble(("Last Used ", "bold"), (last_used, "white")) if last_used else None
        error_line = Text.assemble(
            ("Error Rate ", "bold"),
            (f"{row['error_rate']*100:.1f}%", "white"),
        )
        body_parts = [status_line, "\n", remaining_line]
        if primary_line:
            body_parts.extend(["\n", primary_line])
        if last_used_line:
            body_parts.extend(["\n", last_used_line])
        body_parts.extend(["\n", error_line])
        body = Text.assemble(*body_parts)
        title = f"{row['icon']} {row['label']}"
        console.print(Panel(body, title=title, title_align="left", border_style=row["color"], padding=(1, 2)))


def _limit_display(limit: LimitInfo, label: str) -> tuple[str, str]:
    used_percent = _percent_used(limit.used, limit.limit, limit.remaining)
    percent_text = _format_percent(used_percent)
    reset = _format_reset_hint(limit.reset_hint)
    if percent_text != "n/a" and reset != "-":
        return label, f"{percent_text} | {reset}"
    if percent_text != "n/a":
        return label, percent_text
    if reset != "-":
        return label, reset
    return label, "n/a"


def _select_limits(limits: list[LimitInfo]) -> list[LimitInfo]:
    if not limits:
        return []
    with_window = [limit for limit in limits if limit.window_hours is not None]
    if with_window:
        short = min(with_window, key=lambda limit: limit.window_hours or 0)
        long = max(with_window, key=lambda limit: limit.window_hours or 0)
        if short is long:
            return [short]
        return [long, short]
    return limits[:2]


def _window_label(hours: Optional[float]) -> Optional[str]:
    if hours is None:
        return None
    if hours >= 24:
        days = hours / 24
        if days.is_integer():
            return f"{int(days)}d"
        return f"{days:.1f}d"
    if hours >= 1:
        if hours.is_integer():
            return f"{int(hours)}h"
        return f"{hours:.1f}h"
    minutes = hours * 60
    if minutes.is_integer():
        return f"{int(minutes)}m"
    return f"{minutes:.0f}m"


def _limit_title(limit: LimitInfo) -> str:
    hours = limit.window_hours
    window = _window_label(hours)
    if hours is None:
        return "Limit"
    if hours >= 24 * 5:
        return "Week"
    if window:
        return window
    return "Limit"


def render_accounts_health_dashboard(
    accounts: list[Account], state: State, health: dict[str, HealthInfo], dry_run: bool = False
) -> None:
    ok = warn = red = unknown = 0
    show_source = os.getenv("KMI_SHOW_SOURCE") == "1"
    if dry_run:
        console.print("DRY RUN: upstream requests are simulated.")
    rows = []
    aliases: dict[tuple[str, str], list[str]] = {}
    for account in accounts:
        key = (account.base_url, account.api_key)
        aliases.setdefault(key, []).append(account.label)
    email_by_label = {account.label: account.email for account in accounts if account.email}
    key_to_auth_label: dict[tuple[str, str], str] = {}
    def usage_signature(info: Optional[HealthInfo]) -> Optional[tuple]:
        if info is None:
            return None
        week = None
        rate = None
        for limit in info.limits:
            hours = limit.window_hours or 0
            entry = (
                limit.used,
                limit.limit,
                _reset_seconds(limit.reset_hint),
            )
            if hours >= 24 * 5:
                week = entry
            elif hours <= 6:
                rate = entry
        return (
            info.used,
            info.limit,
            _reset_seconds(info.reset_hint),
            week,
            rate,
        )

    signature_to_label: dict[tuple, str] = {}
    signature_ambiguous: set[tuple] = set()

    for account in accounts:
        if account.label.startswith("current:") or account.id == "current":
            continue
        key_to_auth_label[(account.base_url, account.api_key)] = account.label
        info = health.get(account.id)
        sig = usage_signature(info)
        if sig is None:
            continue
        if sig in signature_to_label:
            signature_ambiguous.add(sig)
        else:
            signature_to_label[sig] = account.label

    for account in accounts:
        info = health.get(account.id)
        status = info.status if info else "unknown"
        status_label, color, icon, group = _status_meta(status)
        if status == "healthy":
            ok += 1
        elif status == "warn":
            warn += 1
        elif status in {"blocked", "exhausted", "disabled"}:
            red += 1
        else:
            unknown += 1

        alias_of = None
        alias_labels = aliases.get((account.base_url, account.api_key), [])
        if len(alias_labels) > 1:
            if account.label.startswith("current:"):
                preferred = [label for label in alias_labels if label != account.label and not label.startswith("current:")]
                alias_of = preferred[0] if preferred else None
            else:
                has_current = any(label.startswith("current:") for label in alias_labels)
                if not has_current:
                    preferred = [label for label in alias_labels if label != account.label]
                    alias_of = preferred[0] if preferred else None
        email = account.email or (info.email if info else None) or (email_by_label.get(alias_of) if alias_of else None)

        matched_label = None
        if account.label.startswith("current:") or account.id == "current":
            matched_label = key_to_auth_label.get((account.base_url, account.api_key))
            if matched_label is None:
                sig = usage_signature(info)
                if sig is not None and sig not in signature_ambiguous:
                    matched_label = signature_to_label.get(sig)

        rows.append(
            {
                "label": account.label,
                "status": status,
                "status_label": status_label,
                "color": color,
                "icon": icon,
                "group": group,
                "is_current": account.label.startswith("current:") or account.id == "current",
                "provider": account.label.split("current:", 1)[1] if account.label.startswith("current:") else None,
                "matched_label": matched_label,
                "remaining": info.remaining_percent if info else None,
                "used": info.used if info else None,
                "limit": info.limit if info else None,
                "remaining_abs": info.remaining if info else None,
                "reset": info.reset_hint if info else None,
                "error_rate": info.error_rate if info else 0.0,
                "last_used": state.keys.get(account.label).last_used if account.label in state.keys else None,
                "source": account.source,
                "limits": info.limits if info else [],
                "alias_of": alias_of,
                "email": email,
            }
        )

    hidden_labels = {
        row["matched_label"]
        for row in rows
        if row.get("matched_label") and row.get("is_current")
    }
    if hidden_labels:
        rows = [row for row in rows if not (row["label"] in hidden_labels and not row["is_current"])]

    def row_reset_seconds(row: dict) -> Optional[int]:
        seconds: list[int] = []
        primary = _reset_seconds(row.get("reset"))
        if primary is not None:
            seconds.append(primary)
        for limit in row.get("limits", []):
            sec = _reset_seconds(limit.reset_hint)
            if sec is not None:
                seconds.append(sec)
        if not seconds:
            return None
        return min(seconds)

    candidates = [
        row
        for row in rows
        if (not row["is_current"])
        and row["status"] not in {"blocked", "exhausted", "disabled"}
        and row["remaining"] is not None
    ]
    if candidates:
        def candidate_key(r: dict) -> tuple:
            reset_sec = row_reset_seconds(r)
            return (
                reset_sec if reset_sec is not None else float("inf"),
                r["remaining"] if r["remaining"] is not None else float("inf"),
                r["label"],
            )

        next_candidate = min(candidates, key=candidate_key)
        next_candidate["highlight_next"] = True

    for row in rows:
        highlight = row.get("highlight_next", False)
        if row["status"] in {"blocked", "exhausted"}:
            row["display_status"] = "EXHAUSTED"
            row["display_icon"] = "🔴"
            row["display_color"] = "red"
            row["display_group"] = 3
        elif row["status"] == "disabled":
            row["display_status"] = "DISABLED"
            row["display_icon"] = "🔴"
            row["display_color"] = "red"
            row["display_group"] = 3
        elif row["status"] == "warn":
            row["display_status"] = "WARN"
            row["display_icon"] = "🟧"
            row["display_color"] = "orange3"
            row["display_group"] = 1
        elif highlight:
            row["display_status"] = "NEXT"
            row["display_icon"] = "🟢"
            row["display_color"] = "green"
            row["display_group"] = 2
        else:
            row["display_status"] = "OK"
            row["display_icon"] = "🟢"
            row["display_color"] = "green"
            row["display_group"] = 2

    rows.sort(
        key=lambda r: (
            0 if r["is_current"] else 1,
            r["display_group"],
            -(r["remaining"] if r["remaining"] is not None else -1.0),
            r["label"],
        )
    )

    # Header panel removed per UX request.

    printed_current = False
    for row in rows:
        status_line = Text.assemble(
            ("Status ", "bold"),
            (f"{row['display_icon']} {row['display_status']}", row["display_color"]),
        )
        email_value = row.get("email")
        email_line = Text.assemble(("Email ", "bold"), (str(email_value), "white")) if email_value else None
        account_hint = None
        if row["is_current"] and row.get("matched_label"):
            account_hint = Text.assemble(("Account ", "bold"), (str(row["matched_label"]), "dim"))
        elif row["is_current"] and row.get("alias_of"):
            account_hint = Text.assemble(("Account ", "bold"), (str(row["alias_of"]), "dim"))
        elif row["is_current"] and row.get("provider"):
            account_hint = Text.assemble(("Account ", "bold"), (str(row["provider"]), "dim"))
        used_limit = _format_used_limit(row["used"], row["limit"])
        if used_limit:
            remaining_line = Text.assemble(
                ("Remaining ", "bold"),
                (_format_percent(row["remaining"]), row["color"]),
                (" | Used ", "bold"),
                (used_limit, "white"),
            )
        else:
            remaining_line = Text.assemble(
                ("Remaining ", "bold"),
                (_format_percent(row["remaining"]), row["color"]),
            )
        primary_reset = _format_reset_hint(row["reset"])
        primary_used_percent = _percent_used(row["used"], row["limit"], row["remaining_abs"])
        primary_summary_parts = []
        if primary_used_percent is not None:
            primary_summary_parts.append(_format_percent(primary_used_percent))
        if primary_reset != "-":
            primary_summary_parts.append(primary_reset)
        primary_line = None
        if primary_summary_parts:
            primary_summary = " | ".join(primary_summary_parts)
            primary_line = Text.assemble(("Week ", "bold"), (primary_summary, "white"))
        last_used = row["last_used"]
        if last_used is not None and str(last_used).strip() == "-":
            last_used = None
        last_used_line = Text.assemble(("Last Used ", "bold"), (last_used, "white")) if last_used else None
        error_line = Text.assemble(
            ("Error Rate ", "bold"),
            (f"{row['error_rate']*100:.1f}%", "white"),
        )
        limits_lines: list[Text] = []
        selected_limits = _select_limits(row["limits"])
        if selected_limits:
            long_limit = selected_limits[0]
            short_limit = selected_limits[-1]
            if short_limit is long_limit:
                label, summary = _limit_display(long_limit, _limit_title(long_limit))
                limits_lines.append(Text.assemble((label + " ", "bold"), (summary, "white")))
            else:
                label, summary = _limit_display(long_limit, _limit_title(long_limit))
                limits_lines.append(Text.assemble((label + " ", "bold"), (summary, "white")))
                label, summary = _limit_display(short_limit, _limit_title(short_limit))
                limits_lines.append(Text.assemble((label + " ", "bold"), (summary, "white")))
        action_line = None
        if row["status"] in {"blocked", "exhausted"}:
            if primary_reset != "-":
                action_line = Text.assemble(("Action ", "bold"), (f"wait reset {primary_reset}", "red"))
            else:
                action_line = Text.assemble(("Action ", "bold"), ("switch to a green key", "red"))
        alias_line = Text.assemble(("Alias of ", "bold"), (row["alias_of"], "dim")) if row["alias_of"] else None
        source_line = Text.assemble(("Source ", "bold"), (row["source"], "dim")) if show_source else None
        has_week_limit = any(
            (limit.window_hours or 0) >= 24 * 5 for limit in selected_limits
        )
        lines: list[Text] = []
        if row["display_status"] != "OK":
            lines.append(status_line)
        if email_line:
            lines.append(email_line)
        if account_hint:
            lines.append(account_hint)
        lines.append(remaining_line)
        if primary_line and not has_week_limit:
            lines.append(primary_line)
        if limits_lines:
            lines.extend(limits_lines)
        if last_used_line:
            lines.append(last_used_line)
        if row["error_rate"] > 0:
            lines.append(error_line)
        if action_line:
            lines.append(action_line)
        if alias_line:
            lines.append(alias_line)
        if source_line:
            lines.append(source_line)
        body = Text()
        for idx, line in enumerate(lines):
            if idx:
                body.append("\n")
            body.append(line)
        display_label = row["label"]
        if row["is_current"]:
            if row.get("matched_label"):
                display_label = f"current:{row['matched_label']}"
            elif row.get("alias_of"):
                display_label = f"current:{row['alias_of']}"
            else:
                display_label = "current"
        title = f"{row['display_icon']} {display_label}"
        if row["is_current"]:
            title = f"⭐ {row['display_icon']} {display_label}"
        console.print(Panel(body, title=title, title_align="left", border_style=row["display_color"], padding=(1, 2)))
        if row["is_current"] and not printed_current:
            console.print()
            printed_current = True
