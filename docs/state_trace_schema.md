# State and Trace Schema

## state.json (schema_version 1)

- schema_version: int
- active_index: int
- rotation_index: int
- auto_rotate: bool
- keys: object keyed by label
  - last_used: ISO8601 UTC timestamp (string or null)
  - request_count: int
  - error_401: int
  - error_403: int
  - error_429: int
  - error_5xx: int
  - exhausted_until: ISO8601 UTC timestamp (string or null)

## trace.jsonl (schema_version 1)

Each line is a JSON object with the following fields:

- schema_version: int
- ts: timestamp string (timezone from KMI_TIMEZONE)
- request_id: hex string
- key_label: string
- key_hash: short hash
- endpoint: string
- status: int
- latency_ms: int
- error_code: string | int | null
- rotation_index: int
