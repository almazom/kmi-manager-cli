from __future__ import annotations

import asyncio
import json
import secrets
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable, Optional, Tuple

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from kmi_manager_cli.config import Config
from kmi_manager_cli.errors import remediation_message
from kmi_manager_cli.keys import Registry
from kmi_manager_cli.logging import get_logger, log_event
from kmi_manager_cli.rotation import mark_exhausted, select_key_for_request
from kmi_manager_cli.state import State, record_request, save_state
from kmi_manager_cli.trace import append_trace, msk_now_str


@dataclass
class ProxyContext:
    config: Config
    registry: Registry
    state: State
    rate_limiter: "RateLimiter"


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
    key = select_key_for_request(ctx.registry, ctx.state, auto_rotate)
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
    app = FastAPI()
    limiter = RateLimiter(config.proxy_max_rps, config.proxy_max_rpm)
    ctx = ProxyContext(config=config, registry=registry, state=state, rate_limiter=limiter)
    logger = get_logger(config)

    @app.api_route(f"{config.proxy_base_path}/{{path:path}}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def proxy(path: str, request: Request) -> Response:
        start = time.perf_counter()
        if not _authorize_request(request, ctx.config.proxy_token):
            log_event(logger, "proxy_unauthorized", endpoint=f"/{path}")
            return JSONResponse({"error": "Unauthorized proxy access"}, status_code=401)
        if not await ctx.rate_limiter.allow():
            log_event(logger, "proxy_rate_limited", endpoint=f"/{path}")
            return JSONResponse({"error": "Proxy rate limit exceeded"}, status_code=429)
        selected = _select_key(ctx)
        if not selected:
            log_event(logger, "no_keys_available", endpoint=f"/{path}")
            return JSONResponse({"error": remediation_message()}, status_code=503)
        key_label, api_key = selected
        key_record = ctx.registry.find_by_label(key_label)
        save_state(ctx.config, ctx.state)

        upstream_url = _build_upstream_url(ctx.config, path, request.url.query)
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        headers["authorization"] = f"Bearer {api_key}"
        body = await request.body()

        if ctx.config.dry_run:
            record_request(ctx.state, key_label, 200)
            save_state(ctx.config, ctx.state)
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
                    "ts_msk": msk_now_str(),
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

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                attempt = 0
                while True:
                    try:
                        resp = await client.request(
                            request.method,
                            upstream_url,
                            headers=headers,
                            content=body,
                        )
                    except httpx.HTTPError as exc:
                        if attempt < ctx.config.proxy_retry_max:
                            delay = (ctx.config.proxy_retry_base_ms * (2 ** attempt)) / 1000.0
                            await asyncio.sleep(delay)
                            attempt += 1
                            continue
                        raise exc

                    if resp.status_code in {429} or 500 <= resp.status_code <= 599:
                        if attempt < ctx.config.proxy_retry_max:
                            delay = (ctx.config.proxy_retry_base_ms * (2 ** attempt)) / 1000.0
                            await asyncio.sleep(delay)
                            attempt += 1
                            continue
                    break
        except httpx.HTTPError as exc:
            record_request(ctx.state, key_label, 503)
            save_state(ctx.config, ctx.state)
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
                    "ts_msk": msk_now_str(),
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
        record_request(ctx.state, key_label, resp.status_code)
        if resp.status_code in {403, 429}:
            mark_exhausted(ctx.state, key_label, ctx.config.rotation_cooldown_seconds)
        save_state(ctx.config, ctx.state)
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
                "ts_msk": msk_now_str(),
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
        return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

    return app


def run_proxy(config: Config, registry: Registry, state: State) -> None:
    import uvicorn

    host, port = parse_listen(config.proxy_listen)
    if not _is_local_host(host) and not config.proxy_allow_remote:
        raise ValueError("Remote proxy binding is disabled. Set KMI_PROXY_ALLOW_REMOTE=1 to override.")
    if not _is_local_host(host) and not config.proxy_token:
        raise ValueError("Remote proxy binding requires KMI_PROXY_TOKEN for authentication.")
    app = create_app(config, registry, state)
    uvicorn.run(app, host=host, port=port)
