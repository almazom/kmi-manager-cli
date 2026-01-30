from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py<3.9 fallback
    ZoneInfo = None


def resolve_timezone(name: Optional[str]) -> timezone:
    if not name or str(name).strip().lower() == "local":
        return datetime.now().astimezone().tzinfo or timezone.utc
    name = str(name).strip()
    upper = name.upper()
    if upper in {"UTC", "GMT", "Z"}:
        return timezone.utc
    if name.startswith(("+", "-")):
        sign = 1 if name[0] == "+" else -1
        raw = name[1:]
        if ":" in raw:
            hours, minutes = raw.split(":", 1)
        else:
            hours, minutes = raw[:2], raw[2:] or "0"
        try:
            offset = timedelta(hours=int(hours), minutes=int(minutes)) * sign
            return timezone(offset)
        except ValueError:
            return timezone.utc
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            return timezone.utc
    return timezone.utc


def format_timestamp(dt: datetime, tz) -> str:
    localized = dt.astimezone(tz)
    suffix = localized.strftime("%z")
    suffix = f" {suffix}" if suffix else ""
    return localized.strftime("%Y-%m-%d %H:%M:%S") + suffix


def now_timestamp(tz_name: Optional[str]) -> str:
    tz = resolve_timezone(tz_name)
    return format_timestamp(datetime.now(timezone.utc), tz)


def parse_iso_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
