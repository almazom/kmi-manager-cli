from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import httpx

from kmi_manager_cli.auth_accounts import Account
from kmi_manager_cli.config import Config
from kmi_manager_cli.logging import get_logger, log_event
from kmi_manager_cli.keys import Registry
from kmi_manager_cli.state import KeyState, State
from kmi_manager_cli.rotation import is_exhausted


@dataclass
class Usage:
    remaining_percent: Optional[float]
    used: Optional[int]
    limit: Optional[int]
    remaining: Optional[int]
    reset_hint: Optional[str]
    raw: dict
    limits: list["LimitInfo"] = field(default_factory=list)
    email: Optional[str] = None


@dataclass
class LimitInfo:
    label: str
    used: Optional[int]
    limit: Optional[int]
    remaining: Optional[int]
    reset_hint: Optional[str]
    window_hours: Optional[float]


@dataclass
class HealthInfo:
    status: str
    remaining_percent: Optional[float]
    used: Optional[int]
    limit: Optional[int]
    remaining: Optional[int]
    reset_hint: Optional[str]
    limits: list[LimitInfo]
    error_rate: float
    email: Optional[str] = None


def _extract_remaining_percent(payload: dict) -> Optional[float]:
    if "remaining_percent" in payload:
        try:
            return float(payload["remaining_percent"])
        except (TypeError, ValueError):
            return None
    if "remaining" in payload and "total" in payload:
        try:
            remaining = float(payload["remaining"])
            total = float(payload["total"])
            return (remaining / total) * 100 if total > 0 else 0.0
        except (TypeError, ValueError):
            return None
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("remaining", "remaining_quota", "remain"):
            if key in data and "total" in data:
                try:
                    remaining = float(data[key])
                    total = float(data["total"])
                    return (remaining / total) * 100 if total > 0 else 0.0
                except (TypeError, ValueError):
                    return None
    return None


def _to_int(value: object) -> Optional[int]:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _extract_reset_hint(payload: dict) -> Optional[str]:
    for key in ("reset_at", "resetAt", "reset_time", "resetTime"):
        if payload.get(key):
            return str(payload.get(key))
    for key in ("reset_in", "resetIn", "ttl", "window"):
        if payload.get(key):
            return f"resets in {payload.get(key)}s"
    return None


def _looks_like_email(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    if "@" in value and "." in value:
        return value.strip()
    return None


def _extract_email_from_payload(payload: dict) -> Optional[str]:
    for key in ("email", "account_email", "user_email"):
        email = _looks_like_email(payload.get(key))
        if email:
            return email
    data = payload.get("data") if isinstance(payload.get("data"), dict) else None
    if data:
        for key in ("email", "account_email", "user_email"):
            email = _looks_like_email(data.get(key))
            if email:
                return email
    account = payload.get("account") if isinstance(payload.get("account"), dict) else None
    if account:
        for key in ("email", "account_email", "user_email"):
            email = _looks_like_email(account.get(key))
            if email:
                return email
    return None


def _window_hours(window: dict) -> Optional[float]:
    duration = _to_int(window.get("duration"))
    if duration is None:
        return None
    time_unit = str(window.get("timeUnit") or "").upper()
    if "MINUTE" in time_unit:
        return duration / 60
    if "HOUR" in time_unit:
        return float(duration)
    if "DAY" in time_unit:
        return float(duration * 24)
    if "WEEK" in time_unit:
        return float(duration * 24 * 7)
    return None


def _limit_label(item: dict, detail: dict, window: dict, idx: int) -> str:
    for key in ("name", "title", "scope"):
        value = item.get(key) or detail.get(key)
        if value:
            return str(value)
    hours = _window_hours(window)
    if hours is not None:
        if hours >= 24 and hours % 24 == 0:
            return f"{int(hours // 24)}d limit"
        if hours.is_integer():
            return f"{int(hours)}h limit"
        return f"{hours:.1f}h limit"
    return f"Limit #{idx + 1}"


def _parse_limits(payload: dict) -> list[LimitInfo]:
    limits_raw = payload.get("limits")
    if not isinstance(limits_raw, list):
        return []
    limits: list[LimitInfo] = []
    for idx, item in enumerate(limits_raw):
        if not isinstance(item, dict):
            continue
        detail = item.get("detail") if isinstance(item.get("detail"), dict) else item
        window = item.get("window") if isinstance(item.get("window"), dict) else {}
        label = _limit_label(item, detail, window, idx)
        used = _to_int(detail.get("used"))
        limit = _to_int(detail.get("limit"))
        remaining = _to_int(detail.get("remaining"))
        reset_hint = _extract_reset_hint(detail)
        limits.append(
            LimitInfo(
                label=label,
                used=used,
                limit=limit,
                remaining=remaining,
                reset_hint=reset_hint,
                window_hours=_window_hours(window),
            )
        )
    return limits


def _extract_usage_summary(payload: dict) -> tuple[Optional[int], Optional[int], Optional[int], Optional[str]]:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    limits = payload.get("limits") if isinstance(payload, dict) else None

    used = limit = remaining = None
    reset_hint = None

    if isinstance(usage, dict):
        used = _to_int(usage.get("used"))
        limit = _to_int(usage.get("limit"))
        remaining = _to_int(usage.get("remaining"))
        reset_hint = _extract_reset_hint(usage)

    if isinstance(limits, list) and limits:
        first = limits[0] if isinstance(limits[0], dict) else None
        if first:
            detail = first.get("detail") if isinstance(first.get("detail"), dict) else first
            used = used if used is not None else _to_int(detail.get("used"))
            limit = limit if limit is not None else _to_int(detail.get("limit"))
            remaining = remaining if remaining is not None else _to_int(detail.get("remaining"))
            if reset_hint is None:
                reset_hint = _extract_reset_hint(detail)

    return used, limit, remaining, reset_hint


def fetch_usage(
    base_url: str,
    api_key: str,
    dry_run: bool = False,
    logger=None,
    label: Optional[str] = None,
) -> Optional[Usage]:
    if dry_run:
        return Usage(
            remaining_percent=100.0,
            used=0,
            limit=100,
            remaining=100,
            reset_hint=None,
            limits=[],
            raw={"dry_run": True},
        )
    url = base_url.rstrip("/") + "/usages"
    try:
        resp = httpx.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=10.0)
        resp.raise_for_status()
        payload = resp.json() if resp.content else {}
    except Exception as exc:
        if logger is not None:
            log_event(
                logger,
                "usage_fetch_failed",
                base_url=base_url,
                key_label=label or "unknown",
                error=str(exc),
            )
        return None
    limits = _parse_limits(payload)
    email = _extract_email_from_payload(payload)
    used, limit, remaining, reset_hint = _extract_usage_summary(payload)
    remaining_percent = _extract_remaining_percent(payload)
    if remaining_percent is None and remaining is not None and limit:
        remaining_percent = round((remaining / limit) * 100, 2)
    if remaining_percent is None and used is not None and limit is not None:
        remaining = remaining if remaining is not None else max(limit - used, 0)
        remaining_percent = round((remaining / limit) * 100, 2) if limit else None
    if remaining_percent is not None and used is not None and limit is not None and limit > 0:
        computed = round(((limit - used) / limit) * 100, 2)
        if abs(remaining_percent - computed) > 1.0:
            remaining_percent = computed
    if remaining_percent is None and limits:
        candidate = max(
            (limit for limit in limits if limit.limit),
            key=lambda limit: limit.window_hours if limit.window_hours is not None else -1,
            default=None,
        )
        if candidate and candidate.limit:
            used = used if used is not None else candidate.used
            limit = limit if limit is not None else candidate.limit
            remaining = remaining if remaining is not None else candidate.remaining
            if used is not None and limit is not None:
                remaining = remaining if remaining is not None else max(limit - used, 0)
                remaining_percent = round((remaining / limit) * 100, 2) if limit else None
    return Usage(
        remaining_percent=remaining_percent,
        used=used,
        limit=limit,
        remaining=remaining,
        reset_hint=reset_hint,
        limits=limits,
        raw=payload,
        email=email,
    )


def score_key(usage: Optional[Usage], key_state: KeyState, exhausted: bool) -> str:
    if exhausted:
        return "exhausted"
    if key_state.error_401 > 0:
        return "blocked"
    if usage and usage.remaining_percent is not None and usage.remaining_percent <= 0:
        return "blocked"

    total = max(key_state.request_count, 1)
    error_rate = (key_state.error_429 + key_state.error_5xx) / total

    if key_state.error_403 > 0:
        return "warn"

    if usage is None:
        return "warn"
    if usage.remaining_percent is not None and usage.remaining_percent < 20:
        return "warn"
    if key_state.error_429 > 0 or key_state.error_5xx > 0 or error_rate >= 0.05:
        return "warn"
    return "healthy"


def get_health_map(config: Config, registry: Registry, state: State) -> dict[str, HealthInfo]:
    health: dict[str, HealthInfo] = {}
    logger = get_logger(config)
    for key in registry.keys:
        usage = fetch_usage(
            config.upstream_base_url,
            key.api_key,
            dry_run=config.dry_run,
            logger=logger,
            label=key.label,
        )
        key_state = state.keys.get(key.label, KeyState())
        total = max(key_state.request_count, 1)
        error_rate = (key_state.error_403 + key_state.error_429 + key_state.error_5xx) / total
        status = score_key(usage, key_state, is_exhausted(state, key.label))
        health[key.label] = HealthInfo(
            status=status,
            remaining_percent=usage.remaining_percent if usage else None,
            used=usage.used if usage else None,
            limit=usage.limit if usage else None,
            remaining=usage.remaining if usage else None,
            reset_hint=usage.reset_hint if usage else None,
            limits=usage.limits if usage else [],
            error_rate=error_rate,
            email=usage.email if usage else None,
        )
    return health


def get_accounts_health(config: Config, accounts: list[Account], state: State, force_real: bool = False) -> dict[str, HealthInfo]:
    health: dict[str, HealthInfo] = {}
    logger = get_logger(config)
    for account in accounts:
        usage = fetch_usage(
            account.base_url,
            account.api_key,
            dry_run=(False if force_real else config.dry_run),
            logger=logger,
            label=account.label,
        )
        key_state = state.keys.get(account.label, KeyState())
        total = max(key_state.request_count, 1)
        error_rate = (key_state.error_403 + key_state.error_429 + key_state.error_5xx) / total
        status = score_key(usage, key_state, is_exhausted(state, account.label))
        health[account.id] = HealthInfo(
            status=status,
            remaining_percent=usage.remaining_percent if usage else None,
            used=usage.used if usage else None,
            limit=usage.limit if usage else None,
            remaining=usage.remaining if usage else None,
            reset_hint=usage.reset_hint if usage else None,
            limits=usage.limits if usage else [],
            error_rate=error_rate,
            email=usage.email if usage else None,
        )
    return health
