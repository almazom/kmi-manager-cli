# KMI Manager CLI - Requirements (raw)

Timestamp (MSK): 2026-01-29 11:00:30 MSK
Source: user brief + on-machine discovery + upstream docs references

## 1) Goal
Create a globally-available wrapper CLI named `kmi` that manages multiple Kimi API keys, supports manual and automatic rotation, and provides traceability to prove round-robin behavior with high confidence. Secrets must not be hard-coded; use .env and external files.

## 2) Primary commands (MVP)
- `kmi --help` : show full help for wrapper
- `kmi --rotate` : manual rotation to the next key
- `kmi --auto_rotate` : enable round-robin auto rotation
- `kmi --trace` : real-time visual trace of which request uses which key

## 3) Key storage and layout
- Standard folder for multiple keys: `_auths/`
  - each key stored as a file (format TBD) or in a single manifest file
- Must support at least 5-7 accounts
- No hard-coded secrets in repo
- Use `.env` for environment config (paths, base URLs, ports, etc.)

## 4) Auth + health signals
- Must be able to determine "health" of each key
  - account quota usage (remaining tokens/requests)
  - errors like 401/429/403
  - latency / timeout counts
- Dashboard (terminal UI) should show:
  - key id (masked)
  - status (healthy/warn/blocked)
  - last used time
  - error count
  - current quota/limit (when available)

## 5) Manual rotation behavior (`--rotate`)
- Switch active key to next available healthy key
- Update runtime state and display dashboard with key list and status
- Must not require editing core Kimi CLI config manually

## 6) Auto rotation behavior (`--auto_rotate`)
- Round-robin rotation per request
- Must be deterministic and provably fair over time
- Keys marked unhealthy should be skipped
- Provide a confidence metric (>=95%) that rotation works
  - e.g., rolling distribution check, chi-square, or quota/usage deltas

## 7) Traceability (`--trace`)
- Real-time view of each request:
  - timestamp
  - selected key (masked)
  - request id / session id
  - target endpoint/model
  - outcome (ok/error)
  - latency
- Provide a "trace window" UI (TUI) or web view
- Must be able to export trace data as JSON logs

## 8) Proxy / routing design
- A local proxy should route requests to Kimi API with per-request key selection
- Proxy API must be unique (non-default path/host) and not obviously generic
- Kimi CLI should be configured to use the proxy as base URL
- Proxy must support Kimi endpoints used by the CLI (chat, models, usage, search/fetch if used)

## 9) Configuration and secrets
- All secrets in `.env` (or external secret manager)
- No secrets stored in Git
- KMI should be able to read config from:
  - `.env`
  - `_auths/` key files
  - optional `kmi.config.toml` or JSON

## 10) UX / interface
- Provide a clear help screen
- Provide a dashboard view for key inventory and status
- Provide usage metrics summary
- Provide clear error messages and remediation hints

## 11) Non-goals (for now)
- Building a full GUI
- Multi-tenant user management
- Automatic account creation

## 12) Open questions
- Exact key file format in `_auths/`
- Whether to store per-key metadata (labels, priority, tags)
- Which endpoints must be proxied for full CLI compatibility
- Where to compute usage/health: direct API or via Kimi CLI usage endpoint

