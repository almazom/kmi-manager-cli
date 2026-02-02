# Trace Schema

Trace file:
- `~/.kmi/trace/trace.jsonl`

Each line is JSON with fields like:
- `ts` (timestamp, per `KMI_TIMEZONE`)
- `request_id`
- `method`
- `endpoint`
- `status`
- `latency_ms`
- `key_label`
- `key_hash`
- `rotation_index`
- `prompt_hint` (trimmed request text)
- `prompt_head` (first word)
- `error_code` (status for errors)
- `schema_version`

Trace is append‑only and rotated based on:
- `KMI_TRACE_MAX_MB`
- `KMI_TRACE_BACKUPS`

