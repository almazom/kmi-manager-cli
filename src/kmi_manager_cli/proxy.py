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
from kmi_manager_cli.health import get_health_map
from kmi_manager_cli.rotation import mark_exhausted, select_key_for_request
from kmi_manager_cli.state import State, record_request, save_state
from kmi_manager_cli.trace import append_trace, trace_now_str

if TYPE_CHECKING:
    from kmi_manager_cli.health import HealthInfo


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


def _build_upstream_headers(request_headers: Iterable[tuple[str, str]], api_key: str) -> dict[str, str]:
    headers = _filter_hop_by_hop_headers(request_headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    headers.pop("authorization", None)
    headers.pop("x-kmi-proxy-token", None)
    headers["authorization"] = f"Bearer {api_key}"
    return headers


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


async def _close_stream(stream_ctx, client: httpx.AsyncClient) -> None:
    if stream_ctx is not None:
        await stream_ctx.__aexit__(None, None, None)
    await client.aclose()


def _get_cached_health(ctx: ProxyContext, ttl_seconds: int = 60) -> dict[str, "HealthInfo"]:
    now = time.time()
    if ctx.health_cache and (now - ctx.health_cache_ts) < ttl_seconds:
        return ctx.health_cache
    health = get_health_map(ctx.config, ctx.registry, ctx.state)
    ctx.health_cache = health
    ctx.health_cache_ts = now
    return health


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
    health_cache: dict[str, "HealthInfo"] = field(default_factory=dict)
    health_cache_ts: float = 0.0


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
        while True:
            await self._flush.wait()
            self._flush.clear()
            await asyncio.sleep(self.debounce_seconds)
            if self._dirty:
                async with self.lock:
                    save_state(self.config, self.state)
                self._dirty = False
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
            log_event(self.logger, "trace_queue_full", dropped=1, dropped_total=self.dropped)
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


@dataclass
class RateLimiter:
    max_rps: int
    max_rpm: int
    recent: Deque[float] = field(default_factory=deque)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def allow(self) -> bool:
        if self.max_rps <= 0 and self.max_rpm <= 0:
            return True
        async with self.lock:
            now = time.time()
            while self.recent and now - self.recent[0] > 60:
                self.recent.popleft()
            if self.max_rpm > 0 and len(self.recent) >= self.max_rpm:
                return False
            if self.max_rps > 0:
                cutoff = now - 1
                rps = 0
                for ts in reversed(self.recent):
                    if ts < cutoff:
                        break
                    rps += 1
                if rps >= self.max_rps:
                    return False
            self.recent.append(now)
            return True


@dataclass
class KeyedRateLimiter:
    max_rps: int
    max_rpm: int
    recent: dict[str, Deque[float]] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def allow(self, key: str) -> bool:
        if self.max_rps <= 0 and self.max_rpm <= 0:
            return True
        async with self.lock:
            now = time.time()
            bucket = self.recent.setdefault(key, deque())
            while bucket and now - bucket[0] > 60:
                bucket.popleft()
            if self.max_rpm > 0 and len(bucket) >= self.max_rpm:
                return False
            if self.max_rps > 0:
                cutoff = now - 1
                rps = 0
                for ts in reversed(bucket):
                    if ts < cutoff:
                        break
                    rps += 1
                if rps >= self.max_rps:
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
    health = _get_cached_health(ctx) if auto_rotate else None
    key = select_key_for_request(ctx.registry, ctx.state, auto_rotate, health=health)
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
    key_limiter = KeyedRateLimiter(config.proxy_max_rps_per_key, config.proxy_max_rpm_per_key)
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
        await ctx.state_writer.start()
        await ctx.trace_writer.start()
        try:
            yield
        finally:
            await ctx.state_writer.stop()
            await ctx.trace_writer.stop()

    app = FastAPI(lifespan=lifespan)
    app.add_event_handler("startup", ctx.state_writer.start)
    app.add_event_handler("startup", ctx.trace_writer.start)
    app.add_event_handler("shutdown", ctx.state_writer.stop)
    app.add_event_handler("shutdown", ctx.trace_writer.stop)

    @app.api_route(f"{config.proxy_base_path}/{{path:path}}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
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
            log_event(logger, "proxy_key_rate_limited", endpoint=f"/{path}", key_label=key_label)
            return JSONResponse({"error": "Per-key rate limit exceeded"}, status_code=429)
        await ctx.state_writer.mark_dirty()

        upstream_url = _build_upstream_url(ctx.config, path, request.url.query)
        headers = _build_upstream_headers(request.headers.items(), api_key)
        body = await request.body()

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
        client = httpx.AsyncClient(timeout=30.0)
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
                        delay = (ctx.config.proxy_retry_base_ms * (2 ** attempt)) / 1000.0
                        await asyncio.sleep(delay)
                        attempt += 1
                        continue
                    raise exc

                if resp.status_code in {429} or 500 <= resp.status_code <= 599:
                    if attempt < ctx.config.proxy_retry_max:
                        await resp.aread()
                        await stream_ctx.__aexit__(None, None, None)
                        stream_ctx = None
                        delay = (ctx.config.proxy_retry_base_ms * (2 ** attempt)) / 1000.0
                        await asyncio.sleep(delay)
                        attempt += 1
                        continue
                break
        except httpx.HTTPError as exc:
            if stream_ctx is not None:
                await stream_ctx.__aexit__(None, None, None)
            await client.aclose()
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
            ctx.trace_writer.enqueue(
                {
                    "ts": trace_now_str(ctx.config),
                    "request_id": uuid.uuid4().hex,
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
                {"error": "Upstream request failed", "hint": "Check connectivity or upstream status."},
                status_code=502,
            )
        async with ctx.state_lock:
            record_request(ctx.state, key_label, resp.status_code)
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
                "key_label": key_label,
                "key_hash": key_record.key_hash if key_record else "",
                "endpoint": f"/{path}",
                "status": resp.status_code,
                "latency_ms": latency_ms,
                "error_code": resp.status_code if resp.status_code >= 400 else None,
                "rotation_index": ctx.state.rotation_index,
            },
        )
        response_headers = _filter_hop_by_hop_headers(resp.headers.items())
        if resp.is_stream_consumed:
            content = resp.content
            await _close_stream(stream_ctx, client)
            return Response(content=content, status_code=resp.status_code, headers=response_headers)
        background = BackgroundTask(_close_stream, stream_ctx, client)
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
        raise ValueError("Remote proxy binding is disabled. Set KMI_PROXY_ALLOW_REMOTE=1 to override.")
    if not _is_local_host(host) and config.proxy_require_tls and not config.proxy_tls_terminated:
        raise ValueError(
            "Remote proxy binding requires TLS termination. "
            "Set KMI_PROXY_TLS_TERMINATED=1 when behind TLS, or set KMI_PROXY_REQUIRE_TLS=0 to override."
        )
    if not _is_local_host(host) and not config.proxy_token:
        raise ValueError("Remote proxy binding requires KMI_PROXY_TOKEN for authentication.")
    app = create_app(config, registry, state)
    uvicorn.run(app, host=host, port=port, lifespan="on")
