# Health Usage Fetch

Source: `src/kmi_manager_cli/health.py`

```python
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
```
