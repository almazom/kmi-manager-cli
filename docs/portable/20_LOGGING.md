# Logging

Log file:
- `~/.kmi/logs/kmi.log`

Format:
- JSON lines with fields: `ts`, `level`, `message`, plus extras.

Rotation:
- `KMI_LOG_MAX_MB`
- `KMI_LOG_BACKUPS`

Common log messages:
- `proxy_request`
- `proxy_upstream_error`
- `usage_fetch_failed`
- `permissions_hardened`
- `insecure_permissions`

