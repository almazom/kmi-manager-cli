# Rotation Policy

Two modes:

## Manual rotation

Command:

```
kmi --rotate
# or
kmi rotate
```

Behavior:
- Picks the "best" key based on health + usage
- Respects `KMI_ROTATE_ON_TIE`
- Can write selected key into `~/.kimi/config.toml` if `KMI_WRITE_CONFIG=1`

## Auto‑rotation

Command:

```
kmi rotate auto
```

Behavior:
- Round‑robin per request (proxy only)
- Enabled only when `KMI_AUTO_ROTATE_ALLOWED=1`
- Uses health info when available

Disable:

```
kmi rotate off
```

