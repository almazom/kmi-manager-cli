# Health and Usage

Health is derived from the upstream `/usages` endpoint.

- Base URL: `KMI_UPSTREAM_BASE_URL`
- Usage endpoint: `${base_url}/usages`

Health data includes:
- remaining percent
- used/limit/remaining
- reset hints
- error rates from proxy state

Commands:

```
kmi --all
kmi --health
kmi --current
```

Notes:
- In dry‑run mode, usage is synthetic (100%).
- If `/usages` fails, health is degraded to warn/unknown.

