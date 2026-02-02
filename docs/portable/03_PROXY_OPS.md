# Proxy Operations

## Start

```
kmi proxy
```

Behavior:
- Detects existing listener on the configured port.
- Stops it automatically.
- Starts a fresh proxy.
- Runs in background by default (logs: `~/.kmi/logs/proxy.out`).
- Use `kmi proxy --foreground` to keep it attached to the terminal.

## Stop

```
kmi proxy-stop --yes
```

## Restart

```
kmi proxy-restart --yes
```

## Logs

```
kmi proxy-logs --no-follow --lines 200
```

App logs (structured):

```
kmi proxy-logs --app --no-follow --lines 200
```

Filter by time (app logs only):

```
kmi proxy-logs --app --since 10m
kmi proxy-logs --app --since 2026-02-02T12:00:00Z
```

## Change port

Edit `.env`:

```
KMI_PROXY_LISTEN=127.0.0.1:54244
```

Then restart proxy and update `KIMI_BASE_URL` in `~/.zshrc` to match.

## Verify listening

```
lsof -nP -iTCP:54244 -sTCP:LISTEN
```
