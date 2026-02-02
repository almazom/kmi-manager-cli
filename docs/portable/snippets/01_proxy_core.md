# Proxy Core (Route + Upstream)

Source: `src/kmi_manager_cli/proxy.py`

## Route handler (core pipeline)

```python
        await ctx.state_writer.start()
        await ctx.trace_writer.start()
        try:
            yield
        finally:
            await ctx.state_writer.stop()
            await ctx.trace_writer.stop()

    # Lifespan manages startup/shutdown for writers; avoid duplicate handlers.
    app = FastAPI(lifespan=lifespan)

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
        prompt_hint, prompt_head = _extract_prompt_meta(body, request.headers.get("content-type", ""))

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
                "method": request.method,
                "prompt_hint": prompt_hint,
                "prompt_head": prompt_head,
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
```

