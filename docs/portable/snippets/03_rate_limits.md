# Rate Limiters (global + per‑key)

Source: `src/kmi_manager_cli/proxy.py`

```python
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
```
