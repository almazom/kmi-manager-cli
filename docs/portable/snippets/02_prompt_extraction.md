# Prompt Extraction (hint + first word)

Source: `src/kmi_manager_cli/proxy.py`

```python
def _coerce_prompt_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("text") if isinstance(value.get("text"), str) else ""
        if text:
            return text
        content = value.get("content")
        if isinstance(content, str):
            return content
        return ""
    if isinstance(value, list):
        for item in value:
            text = _coerce_prompt_text(item)
            if text:
                return text
    return ""


def _trim_prompt(text: str, max_words: int = 6, max_chars: int = 60) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    words = cleaned.split(" ")
    trimmed = " ".join(words[:max_words])
    if len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars].rstrip()
    if trimmed != cleaned:
        return trimmed + "..."
    return trimmed


def _first_word(text: str) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    return cleaned.split(" ", 1)[0]


def _extract_prompt_meta(body: bytes, content_type: str) -> tuple[str, str]:
    if not body or "json" not in content_type.lower():
        return "", ""
    try:
        payload = json.loads(body.decode("utf-8", errors="ignore"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "", ""
    text = ""
    if isinstance(payload, dict):
        messages = payload.get("messages")
        if isinstance(messages, list):
            for msg in reversed(messages):
                if isinstance(msg, dict):
                    text = _coerce_prompt_text(msg.get("content"))
                    if text:
                        break
        if not text:
            for key in ("prompt", "input", "query", "text"):
                if isinstance(payload.get(key), str):
                    text = payload.get(key, "")
                    break
    if not text:
        return "", ""
    return _trim_prompt(text), _first_word(text)

```
