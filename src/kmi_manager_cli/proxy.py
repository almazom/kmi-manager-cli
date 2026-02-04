from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import json
import secrets
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Deque, Iterable, Optional, Tuple, TYPE_CHECKING

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from kmi_manager_cli.config import Config
from kmi_manager_cli.errors import remediation_message
from kmi_manager_cli.keys import Registry
from kmi_manager_cli.logging import get_logger, log_event
from kmi_manager_cli.health import fetch_usage, get_health_map
from kmi_manager_cli.rotation import (
    clear_blocked,
    is_blocked,
    mark_blocked,
    mark_exhausted,
    select_key_for_request,
)
from kmi_manager_cli.state import State, record_request, save_state
from kmi_manager_cli.trace import append_trace, trace_now_str

if TYPE_CHECKING:
    from kmi_manager_cli.health import HealthInfo


"""FastAPI-based async proxy server for request forwarding.

This module implements the KMI proxy that sits between clients and the upstream
API, handling key selection, rate limiting, retries, and error detection.

Key Components:
    create_app: Builds FastAPI application with all routes and middleware
    ProxyContext: Shared state container (registry, state, limiters, writers)
    RateLimiter: Token bucket rate limiter for global proxy limits
    KeyedRateLimiter: Per-key rate limiting
    StateWriter: Debounced async state persistence
    TraceWriter: Async trace logging with queue

Request Flow:
    1. Token authentication (_authorize_request)
    2. Global rate limit check (RateLimiter)
    3. Key selection (select_key_for_request)
    4. Per-key rate limit check (KeyedRateLimiter)
    5. Upstream request with retry logic
    6. Error detection (402/403/429/5xx handling)
    7. State update and trace write

Features:
    - Streaming response support
    - Payment error detection (blocks keys with billing issues)
    - Retry with exponential backoff
    - Background health refresh loop
    - Blocklist rechecking for recovery
"""


_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

_PAYMENT_ERROR_TOKENS = (
    "payment",
    "payment_required",
    "natpament",
    "notpayment",
    "billing",
    "balance",
    "insufficient_balance",
    "insufficient_quota",
    "balance_insufficient",
    "credit",
    "subscription",
    "plan",
    "top up",
    "top-up",
    "recharge",
    "\u4f59\u989d\u4e0d\u8db3",
    "\u8d26\u6237\u4f59\u989d\u4e0d\u8db3",
    "\u8bf7\u5145\u503c",
    "\u5145\u503c",
    "\u6b20\u8d39",
    "\u672a\u4ed8\u8d39",
    "\u672a\u652f\u4ed8",
    "\u8ba2\u9605",
    "\u5957\u9910",
)
_ERROR_FIELDS = {
    "error",
    "message",
    "code",
    "error_code",
    "errorcode",
    "err_code",
    "errcode",
    "type",
    "detail",
    "title",
    "status",
    "status_code",
    "reason",
}


def _filter_hop_by_hop_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    connection_tokens: set[str] = set()
    for key, value in headers:
        if key.lower() == "connection":
            for token in value.split(","):
                token = token.strip().lower()
                if token:
                    connection_tokens.add(token)
    hop_by_hop = _HOP_BY_HOP_HEADERS | connection_tokens
    filtered: dict[str, str] = {}
    for key, value in headers:
        if key.lower() in hop_by_hop:
            continue
        filtered[key] = value
    return filtered


def _build_upstream_headers(
    request_headers: Iterable[tuple[str, str]], api_key: str
) -> dict[str, str]:
    headers = _filter_hop_by_hop_headers(request_headers)
    for key in list(headers):
        if key.lower() in {"host", "content-length", "authorization", "x-kmi-proxy-token"}:
            headers.pop(key, None)
    headers["authorization"] = f"Bearer {api_key}"
    return headers


def _coerce_prompt_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("text") if isinstance(value.get("text"), str) else ""
        if text:
            return text
        content = value.get("content")
        if isinstance(content, str):
            return content
        return ""
    if isinstance(value, list):
        for item in value:
            text = _coerce_prompt_text(item)
            if text:
                return text
    return ""


def _trim_prompt(text: str, max_words: int = 6, max_chars: int = 60) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    words = cleaned.split(" ")
    trimmed = " ".join(words[:max_words])
    if len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars].rstrip()
    if trimmed != cleaned:
        return trimmed + "..."
    return trimmed


def _first_word(text: str) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    return cleaned.split(" ", 1)[0]


def _extract_prompt_meta(body: bytes, content_type: str) -> tuple[str, str]:
    if not body or "json" not in content_type.lower():
        return "", ""
    try:
        payload = json.loads(body.decode("utf-8", errors="ignore"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "", ""
    text = ""
    if isinstance(payload, dict):
        messages = payload.get("messages")
        if isinstance(messages, list):
            for msg in reversed(messages):
                if isinstance(msg, dict):
                    text = _coerce_prompt_text(msg.get("content"))
                    if text:
                        break
        if not text:
            for key in ("prompt", "input", "query", "text"):
                if isinstance(payload.get(key), str):
                    text = payload.get(key, "")
                    break
    if not text:
        return "", ""
    return _trim_prompt(text), _first_word(text)


def _parse_retry_after(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        seconds = int(value)
        return max(0, seconds)
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = int((dt - datetime.now(timezone.utc)).total_seconds())
        return max(0, delta)


def _collect_error_strings(payload: object, bucket: list[str], depth: int = 0) -> None:
    if depth > 100:  # Limit recursion to prevent stack overflow
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_lower = str(key).lower()
            if key_lower in _ERROR_FIELDS:
                _collect_error_strings(value, bucket, depth + 1)
                continue
            if isinstance(value, str) and key_lower.startswith("error"):
                bucket.append(value)
        return
    if isinstance(payload, list):
        for item in payload:
            _collect_error_strings(item, bucket, depth + 1)
        return
    if isinstance(payload, (str, int, float)):
        bucket.append(str(payload))


def _extract_error_hint(content: bytes, content_type: str) -> str:
    if not content:
        return ""
    text = content.decode("utf-8", errors="ignore").strip()
    if not text:
        return ""
    if "json" in (content_type or "").lower() or text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text
        parts: list[str] = []
        _collect_error_strings(payload, parts)
        return " ".join(parts) if parts else text
    return text


def _looks_like_payment_error(status_code: int, hint: str) -> bool:
    if status_code == 402:
        return True
    if status_code not in {400, 403}:
        return False
    lowered = hint.lower()
    return any(token in lowered for token in _PAYMENT_ERROR_TOKENS)


async def _close_stream(stream_ctx, client: Optional[httpx.AsyncClient]) -> None:
    if stream_ctx is not None:
        await stream_ctx.__aexit__(None, None, None)
    # Note: client is now shared and managed by lifespan, don't close it here


def _get_cached_health(ctx: ProxyContext) -> dict[str, "HealthInfo"]:
    return ctx.health_cache


async def _maybe_refresh_health(ctx: ProxyContext) -> None:
    interval = ctx.config.usage_cache_seconds
    if interval <= 0:
        return
    now = time.time()
    async with ctx.state_lock:
        if ctx.health_cache_ts and (now - ctx.health_cache_ts) < interval:
            return
    health = await asyncio.to_thread(
        get_health_map, ctx.config, ctx.registry, ctx.state
    )
    async with ctx.state_lock:
        ctx.health_cache = health
        ctx.health_cache_ts = now
        ctx.state.last_health_refresh = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    await ctx.state_writer.mark_dirty()


async def _maybe_recheck_blocked(ctx: ProxyContext) -> None:
    interval = ctx.config.blocklist_recheck_seconds
    if interval <= 0:
        return
    now = time.time()
    if (now - ctx.blocklist_recheck_ts) < interval:
        return
    ctx.blocklist_recheck_ts = now

    candidates: list[tuple[str, str]] = []
    async with ctx.state_lock:
        for key in ctx.registry.keys:
            if not is_blocked(ctx.state, key.label):
                continue
            candidates.append((key.label, key.api_key))
            if (
                ctx.config.blocklist_recheck_max > 0
                and len(candidates) >= ctx.config.blocklist_recheck_max
            ):
                break

    if not candidates:
        return

    cleared: list[str] = []
    for label, api_key in candidates:
        usage = await asyncio.to_thread(
            fetch_usage,
            ctx.config.upstream_base_url,
            api_key,
            False,
            get_logger(ctx.config),
            label,
        )
        if usage is not None:
            cleared.append(label)

    if not cleared:
        return

    async with ctx.state_lock:
        for label in cleared:
            clear_blocked(ctx.state, label)
    await ctx.state_writer.mark_dirty()


async def _health_refresh_loop(ctx: ProxyContext) -> None:
    logger = get_logger(ctx.config)
    while not ctx.health_stop.is_set():
        try:
            await _maybe_refresh_health(ctx)
            await _maybe_recheck_blocked(ctx)
        except Exception as exc:
            log_event(logger, "health_refresh_error", error=str(exc))
        try:
            await asyncio.wait_for(ctx.health_stop.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            continue


@dataclass
class ProxyContext:
    config: Config
    registry: Registry
    state: State
    rate_limiter: "RateLimiter"
    key_rate_limiter: "KeyedRateLimiter"
    state_lock: asyncio.Lock
    state_writer: "StateWriter"
    trace_writer: "TraceWriter"
    http_client: Optional[httpx.AsyncClient] = None
    health_cache: dict[str, "HealthInfo"] = field(default_factory=dict)
    health_cache_ts: float = 0.0
    blocklist_recheck_ts: float = 0.0
    health_stop: asyncio.Event = field(default_factory=asyncio.Event)
    health_task: Optional[asyncio.Task] = None


@dataclass
class StateWriter:
    config: Config
    state: State
    lock: asyncio.Lock
    debounce_seconds: float = 0.05
    _dirty: bool = False
    _flush: asyncio.Event = field(default_factory=asyncio.Event)
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def mark_dirty(self) -> None:
        self._dirty = True
        if self._task is None:
            async with self.lock:
                save_state(self.config, self.state)
            self._dirty = False
            return
        self._flush.set()

    async def stop(self) -> None:
        self._stop.set()
        self._flush.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        logger = get_logger(self.config)
        while True:
            await self._flush.wait()
            self._flush.clear()
            await asyncio.sleep(self.debounce_seconds)
            if self._dirty:
                try:
                    async with self.lock:
                        save_state(self.config, self.state)
                    self._dirty = False
                except Exception as exc:
                    log_event(logger, "state_save_failed", error=str(exc))
            if self._stop.is_set():
                break


@dataclass
class TraceWriter:
    config: Config
    logger: "logging.Logger"
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=1000))
    dropped: int = 0
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    def enqueue(self, entry: dict) -> None:
        if self._task is None:
            try:
                append_trace(self.config, entry)
            except Exception as exc:  # pragma: no cover - defensive
                log_event(self.logger, "trace_write_failed", error=str(exc))
            return
        if self.queue.full():
            self.dropped += 1
            log_event(
                self.logger, "trace_queue_full", dropped=1, dropped_total=self.dropped
            )
            return
        self.queue.put_nowait(entry)

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        while True:
            try:
                entry = await asyncio.wait_for(self.queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                if self._stop.is_set() and self.queue.empty():
                    break
                continue
            try:
                append_trace(self.config, entry)
            except Exception as exc:  # pragma: no cover - defensive
                log_event(self.logger, "trace_write_failed", error=str(exc))


def _check_rate_limits(recent: Deque[float], max_rps: int, max_rpm: int, now: float) -> bool:
    """Check if request is within rate limits. Returns True if allowed."""
    # Clean old entries
    while recent and now - recent[0] > 60:
        recent.popleft()
    
    # Check per-minute limit
    if max_rpm > 0 and len(recent) >= max_rpm:
        return False
    
    # Check per-second limit
    if max_rps > 0:
        cutoff = now - 1
        rps = sum(1 for ts in reversed(recent) if ts >= cutoff)
        if rps >= max_rps:
            return False
    
    return True


@dataclass
class RateLimiter:
    """Token bucket rate limiter for global proxy limits."""
    max_rps: int
    max_rpm: int
    recent: Deque[float] = field(default_factory=lambda: deque(maxlen=10000))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def allow(self) -> bool:
        """Check if a request is allowed under current rate limits."""
        if self.max_rps <= 0 and self.max_rpm <= 0:
            return True
        async with self.lock:
            now = time.time()
            if not _check_rate_limits(self.recent, self.max_rps, self.max_rpm, now):
                return False
            self.recent.append(now)
            return True


@dataclass
class KeyedRateLimiter:
    """Per-key rate limiter with separate buckets for each key."""
    max_rps: int
    max_rpm: int
    recent: dict[str, Deque[float]] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def allow(self, key: str) -> bool:
        """Check if a request for the given key is allowed under current rate limits."""
        if self.max_rps <= 0 and self.max_rpm <= 0:
            return True
        async with self.lock:
            now = time.time()
            bucket = self.recent.setdefault(key, deque(maxlen=10000))
            if not _check_rate_limits(bucket, self.max_rps, self.max_rpm, now):
                return False
            bucket.append(now)
            return True


def parse_listen(listen: str) -> Tuple[str, int]:
    if ":" not in listen:
        raise ValueError("KMI_PROXY_LISTEN must be in host:port format")
    host, port_raw = listen.rsplit(":", 1)
    return host, int(port_raw)


def _build_upstream_url(config: Config, path: str, query: str) -> str:
    base = config.upstream_base_url.rstrip("/")
    path = path.lstrip("/")
    url = f"{base}/{path}" if path else base
    if query:
        url = f"{url}?{query}"
    return url


def _select_key(ctx: ProxyContext) -> Optional[tuple[str, str]]:
    auto_rotate = ctx.state.auto_rotate and ctx.config.auto_rotate_allowed
    require_usage = ctx.config.require_usage_before_request
    health = _get_cached_health(ctx) if (auto_rotate or require_usage) else None
    key = select_key_for_request(
        ctx.registry,
        ctx.state,
        auto_rotate,
        health=health,
        require_usage_ok=require_usage,
        fail_open_on_empty_cache=ctx.config.fail_open_on_empty_cache,
        include_warn=ctx.config.rotate_include_warn,
    )
    if not key:
        return None
    return key.label, key.api_key


def _is_local_host(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def _authorize_request(request: Request, token: str) -> bool:
    if not token:
        return True
    auth_header = request.headers.get("authorization", "")
    provided = ""
    if auth_header.lower().startswith("bearer "):
        provided = auth_header.split(" ", 1)[1].strip()
    if not provided:
        provided = request.headers.get("x-kmi-proxy-token", "").strip()
    return secrets.compare_digest(provided, token)


def create_app(config: Config, registry: Registry, state: State) -> FastAPI:
    limiter = RateLimiter(config.proxy_max_rps, config.proxy_max_rpm)
    logger = get_logger(config)
    key_limiter = KeyedRateLimiter(
        config.proxy_max_rps_per_key, config.proxy_max_rpm_per_key
    )
    state_lock = asyncio.Lock()
    state_writer = StateWriter(config=config, state=state, lock=state_lock)
    trace_writer = TraceWriter(config=config, logger=logger)
    ctx = ProxyContext(
        config=config,
        registry=registry,
        state=state,
        rate_limiter=limiter,
        key_rate_limiter=key_limiter,
        state_lock=state_lock,
        state_writer=state_writer,
        trace_writer=trace_writer,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        ctx.http_client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_connections=100, max_keepalive_connections=20))
        await ctx.state_writer.start()
        await ctx.trace_writer.start()
        ctx.health_task = asyncio.create_task(_health_refresh_loop(ctx))
        try:
            yield
        finally:
            ctx.health_stop.set()
            if ctx.health_task:
                await ctx.health_task
            await ctx.state_writer.stop()
            await ctx.trace_writer.stop()
            if ctx.http_client:
                await ctx.http_client.aclose()

    # Lifespan manages startup/shutdown for writers; avoid duplicate handlers.
    app = FastAPI(lifespan=lifespan)

    @app.api_route(
        f"{config.proxy_base_path}/{{path:path}}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )
    async def proxy(path: str, request: Request) -> Response:
        start = time.perf_counter()
        if not _authorize_request(request, ctx.config.proxy_token):
            log_event(logger, "proxy_unauthorized", endpoint=f"/{path}")
            return JSONResponse(
                {
                    "error": "Unauthorized proxy access",
                    "hint": "Send Authorization: Bearer <token> or x-kmi-proxy-token header.",
                },
                status_code=401,
            )
        if not await ctx.rate_limiter.allow():
            log_event(logger, "proxy_rate_limited", endpoint=f"/{path}")
            return JSONResponse({"error": "Proxy rate limit exceeded"}, status_code=429)
        async with ctx.state_lock:
            prev_active = ctx.state.active_index
            prev_rotation = ctx.state.rotation_index
            selected = _select_key(ctx)
            if not selected:
                log_event(logger, "no_keys_available", endpoint=f"/{path}")
                return JSONResponse({"error": remediation_message()}, status_code=503)
            key_label, api_key = selected
            key_record = ctx.registry.find_by_label(key_label)
        if not await ctx.key_rate_limiter.allow(key_label):
            async with ctx.state_lock:
                ctx.state.active_index = prev_active
                ctx.state.rotation_index = prev_rotation
            await ctx.state_writer.mark_dirty()
            log_event(
                logger,
                "proxy_key_rate_limited",
                endpoint=f"/{path}",
                key_label=key_label,
            )
            return JSONResponse(
                {"error": "Per-key rate limit exceeded"}, status_code=429
            )
        await ctx.state_writer.mark_dirty()

        upstream_url = _build_upstream_url(ctx.config, path, request.url.query)
        headers = _build_upstream_headers(request.headers.items(), api_key)
        body = await request.body()
        prompt_hint, prompt_head = _extract_prompt_meta(
            body, request.headers.get("content-type", "")
        )

        if ctx.config.dry_run:
            async with ctx.state_lock:
                record_request(ctx.state, key_label, 200)
            await ctx.state_writer.mark_dirty()
            latency_ms = int((time.perf_counter() - start) * 1000)
            log_event(
                logger,
                "proxy_request",
                endpoint=f"/{path}",
                status=200,
                key_label=key_label,
                latency_ms=latency_ms,
            )
            append_trace(
                ctx.config,
                {
                    "ts": trace_now_str(ctx.config),
                    "request_id": uuid.uuid4().hex,
                    "method": request.method,
                    "prompt_hint": prompt_hint,
                    "prompt_head": prompt_head,
                    "key_label": key_label,
                    "key_hash": key_record.key_hash if key_record else "",
                    "endpoint": f"/{path}",
                    "status": 200,
                    "latency_ms": latency_ms,
                    "error_code": None,
                    "rotation_index": ctx.state.rotation_index,
                },
            )
            return JSONResponse(
                {
                    "dry_run": True,
                    "upstream_url": upstream_url,
                    "method": request.method,
                    "path": path,
                    "key_label": key_label,
                },
                status_code=200,
            )

        stream_ctx = None
        client = ctx.http_client
        if client is None:
            # Lazy initialization for tests that don't use lifespan
            client = httpx.AsyncClient(timeout=30.0)
            ctx.http_client = client
        try:
            attempt = 0
            while True:
                try:
                    stream_ctx = client.stream(
                        request.method,
                        upstream_url,
                        headers=headers,
                        content=body,
                    )
                    resp = await stream_ctx.__aenter__()
                except httpx.HTTPError as exc:
                    if attempt < ctx.config.proxy_retry_max:
                        delay = (ctx.config.proxy_retry_base_ms * (2**attempt)) / 1000.0
                        await asyncio.sleep(delay)
                        attempt += 1
                        continue
                    raise exc

                if resp.status_code in {429} or 500 <= resp.status_code <= 599:
                    if attempt < ctx.config.proxy_retry_max:
                        await resp.aread()
                        await stream_ctx.__aexit__(None, None, None)
                        stream_ctx = None
                        delay = (ctx.config.proxy_retry_base_ms * (2**attempt)) / 1000.0
                        await asyncio.sleep(delay)
                        attempt += 1
                        continue
                break
        except httpx.HTTPError as exc:
            if stream_ctx is not None:
                await stream_ctx.__aexit__(None, None, None)
            async with ctx.state_lock:
                record_request(ctx.state, key_label, 503)
            await ctx.state_writer.mark_dirty()
            latency_ms = int((time.perf_counter() - start) * 1000)
            log_event(
                logger,
                "proxy_upstream_error",
                endpoint=f"/{path}",
                status=503,
                key_label=key_label,
                latency_ms=latency_ms,
                error=str(exc),
            )
            append_trace(
                ctx.config,
                {
                    "ts": trace_now_str(ctx.config),
                    "request_id": uuid.uuid4().hex,
                    "method": request.method,
                    "prompt_hint": prompt_hint,
                    "prompt_head": prompt_head,
                    "key_label": key_label,
                    "key_hash": key_record.key_hash if key_record else "",
                    "endpoint": f"/{path}",
                    "status": 503,
                    "latency_ms": latency_ms,
                    "error_code": "upstream_error",
                    "rotation_index": ctx.state.rotation_index,
                },
            )
            return JSONResponse(
                {
                    "error": "Upstream request failed",
                    "hint": "Check connectivity or upstream status.",
                },
                status_code=502,
            )
        content: Optional[bytes] = None
        error_hint = ""
        payment_required = False
        if resp.status_code >= 400:
            content = await resp.aread()
            error_hint = _extract_error_hint(
                content, resp.headers.get("content-type", "")
            )
            payment_required = _looks_like_payment_error(resp.status_code, error_hint)
        async with ctx.state_lock:
            record_request(ctx.state, key_label, resp.status_code)
            if payment_required:
                mark_blocked(
                    ctx.state,
                    key_label,
                    reason="payment_required",
                    block_seconds=ctx.config.payment_block_seconds,
                )
                log_event(
                    logger,
                    "proxy_key_blocked",
                    key_label=key_label,
                    reason="payment_required",
                )
            if resp.status_code in {403, 429} or 500 <= resp.status_code <= 599:
                cooldown = ctx.config.rotation_cooldown_seconds
                if resp.status_code == 429:
                    retry_after = _parse_retry_after(resp.headers.get("retry-after"))
                    if retry_after is not None:
                        cooldown = max(1, retry_after)
                elif 500 <= resp.status_code <= 599:
                    cooldown = min(ctx.config.rotation_cooldown_seconds, 60)
                mark_exhausted(ctx.state, key_label, cooldown)
        await ctx.state_writer.mark_dirty()
        latency_ms = int((time.perf_counter() - start) * 1000)
        log_event(
            logger,
            "proxy_request",
            endpoint=f"/{path}",
            status=resp.status_code,
            key_label=key_label,
            latency_ms=latency_ms,
        )
        append_trace(
            ctx.config,
            {
                "ts": trace_now_str(ctx.config),
                "request_id": uuid.uuid4().hex,
                "method": request.method,
                "prompt_hint": prompt_hint,
                "prompt_head": prompt_head,
                "key_label": key_label,
                "key_hash": key_record.key_hash if key_record else "",
                "endpoint": f"/{path}",
                "status": resp.status_code,
                "latency_ms": latency_ms,
                "error_code": "payment_required"
                if payment_required
                else (resp.status_code if resp.status_code >= 400 else None),
                "rotation_index": ctx.state.rotation_index,
            },
        )
        response_headers = _filter_hop_by_hop_headers(resp.headers.items())
        if resp.is_stream_consumed:
            content = resp.content if content is None else content
            await _close_stream(stream_ctx, None)
            return Response(
                content=content, status_code=resp.status_code, headers=response_headers
            )
        background = BackgroundTask(_close_stream, stream_ctx, None)
        return StreamingResponse(
            resp.aiter_raw(),
            status_code=resp.status_code,
            headers=response_headers,
            background=background,
        )

    return app


def run_proxy(config: Config, registry: Registry, state: State) -> None:
    import uvicorn

    host, port = parse_listen(config.proxy_listen)
    if not _is_local_host(host) and not config.proxy_allow_remote:
        raise ValueError(
            "Remote proxy binding is disabled. Set KMI_PROXY_ALLOW_REMOTE=1 to override."
        )
    if (
        not _is_local_host(host)
        and config.proxy_require_tls
        and not config.proxy_tls_terminated
    ):
        raise ValueError(
            "Remote proxy binding requires TLS termination. "
            "Set KMI_PROXY_TLS_TERMINATED=1 when behind TLS, or set KMI_PROXY_REQUIRE_TLS=0 to override."
        )
    if not _is_local_host(host) and not config.proxy_token:
        raise ValueError(
            "Remote proxy binding requires KMI_PROXY_TOKEN for authentication."
        )
    app = create_app(config, registry, state)
    uvicorn.run(app, host=host, port=port, lifespan="on")
