+---------------------------+
| CLI (Typer)               |
| - kmi --rotate            |
| - kmi --auto_rotate       |
| - kmi --trace             |
| - kmi proxy               |
+-------------+-------------+
              |
              v
+---------------------------+
| Core Logic                |
| config | keys | rotation  |
| health | state | trace    |
| ui     | logging           |
+------+------+-------------+
       |      |
       |      v
       |   Local Files
       |   - state.json
       |   - trace.jsonl
       |   - logs/kmi.log
       |
       v
+---------------------------+
| Local Proxy (FastAPI)     |
| httpx -> upstream         |
+-------------+-------------+
              |
              v
+---------------------------+
| Kimi API (upstream)       |
| /chat/completions         |
| /models /usages           |
+---------------------------+
