from __future__ import annotations

import json

from kmi_manager_cli import proxy as proxy_module


def test_filter_hop_by_hop_headers() -> None:
    headers = [
        ("Connection", "keep-alive, x-test"),
        ("Keep-Alive", "timeout=5"),
        ("Transfer-Encoding", "chunked"),
        ("X-Test", "should-drop"),
        ("X-Other", "keep"),
    ]
    filtered = proxy_module._filter_hop_by_hop_headers(headers)
    assert "keep-alive" not in filtered
    assert "transfer-encoding" not in {k.lower() for k in filtered}
    assert "x-test" not in {k.lower() for k in filtered}
    assert filtered.get("X-Other") == "keep"


def test_build_upstream_headers_overrides_authorization() -> None:
    headers = [
        ("Host", "example.com"),
        ("Content-Length", "10"),
        ("Authorization", "Bearer old"),
        ("X-KMI-Proxy-Token", "secret"),
        ("X-Extra", "1"),
    ]
    built = proxy_module._build_upstream_headers(headers, "sk-new")
    assert built["authorization"] == "Bearer sk-new"
    assert "host" not in {k.lower() for k in built}
    assert "content-length" not in {k.lower() for k in built}
    assert built["X-Extra"] == "1"


def test_trim_prompt_limits_words() -> None:
    text = "one two three four five six seven"
    trimmed = proxy_module._trim_prompt(text)
    assert trimmed.endswith("...")
    assert trimmed.startswith("one two three four five six")


def test_extract_prompt_meta_from_messages() -> None:
    payload = {"messages": [{"role": "user", "content": "hello world"}]}
    body = json.dumps(payload).encode("utf-8")
    head, hint = proxy_module._extract_prompt_meta(body, "application/json")
    assert head == "hello world"
    assert hint == "hello"


def test_parse_retry_after() -> None:
    assert proxy_module._parse_retry_after("120") == 120
    assert proxy_module._parse_retry_after("abc") is None
    assert proxy_module._parse_retry_after("") is None
    assert proxy_module._parse_retry_after(None) is None


def test_extract_error_hint_and_payment_detection() -> None:
    payload = {"error": {"message": "Payment required"}}
    content = json.dumps(payload).encode("utf-8")
    hint = proxy_module._extract_error_hint(content, "application/json")
    assert "Payment required" in hint
    assert proxy_module._looks_like_payment_error(402, hint) is True
    assert proxy_module._looks_like_payment_error(403, hint) is True
    assert proxy_module._looks_like_payment_error(400, "other error") is False
