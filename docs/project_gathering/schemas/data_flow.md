Manual rotate flow:
User -> kmi --rotate
  -> load_config (.env)
  -> load_auths_dir (_auths)
  -> load_state (~/.kmi/state.json)
  -> get_health_map (/usages)
  -> rotate_manual (most resourceful)
  -> save_state
  -> render dashboard

Proxy request flow:
Client -> http://host:port/base_path/...
  -> FastAPI route
  -> select_key_for_request (round-robin if auto)
  -> inject Authorization: Bearer <key>
  -> httpx request to upstream
  -> record_request + mark_exhausted (on 403/429)
  -> append_trace (trace.jsonl)
  -> response to client
