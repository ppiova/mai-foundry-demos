"""Contract tests for the MAI-Thinking-1 request/response handling.

These lock in behaviour that was verified against a live deployment (see
docs/API_VERIFIED.md) so a future refactor can't silently regress it:

* the request body must use ``max_completion_tokens`` (``max_tokens`` is rejected
  with HTTP 400 by the service) and must omit unset optional fields;
* the native ``/mai/v1/`` chat path is used, because only it accepts
  ``reasoning_display``;
* streamed tool calls arrive complete-per-chunk with an ``id`` and no ``index``;
* an error event inside the stream must raise instead of returning partial text.
"""

from __future__ import annotations

import json

import pytest

from mai.client import MAIClient, MAIStreamError
from mai.config import Config


def _client(**overrides) -> MAIClient:
    cfg = Config(
        foundry_endpoint="https://example.services.ai.azure.com",
        foundry_api_key="k",
        thinking_deployment="MAI-Thinking-1",
        **overrides,
    )
    return MAIClient(cfg)


# ── request contract ────────────────────────────────────────────────────────────
def test_chat_url_uses_native_mai_path():
    assert _client().cfg.chat_url.endswith("/mai/v1/chat/completions")


def test_payload_uses_max_completion_tokens_not_max_tokens():
    payload = _client()._chat_payload(
        [{"role": "user", "content": "hi"}], None, None, None, 64, None
    )
    assert payload["max_completion_tokens"] == 64
    assert "max_tokens" not in payload


def test_payload_omits_unset_optionals():
    payload = _client()._chat_payload(
        [{"role": "user", "content": "hi"}], None, None, None, None, None
    )
    assert set(payload) == {"model", "messages"}


def test_tool_choice_only_sent_alongside_tools():
    tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    cl = _client()
    assert "tool_choice" not in cl._chat_payload([], tools, None, None, None, None)
    assert cl._chat_payload([], tools, "auto", None, None, None)["tool_choice"] == "auto"
    # tool_choice without tools is meaningless and must not be sent
    assert "tool_choice" not in cl._chat_payload([], None, "auto", None, None, None)


def test_reasoning_display_is_forwarded():
    payload = _client()._chat_payload([], None, None, None, None, "encrypted")
    assert payload["reasoning_display"] == "encrypted"


# ── streaming contract ──────────────────────────────────────────────────────────
class _FakeResponse:
    """Minimal stand-in for a streamed ``requests`` response."""

    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self):
        for line in self._lines:
            yield line.encode("utf-8")


def _sse(*payloads) -> list[str]:
    return [f"data: {json.dumps(p)}" for p in payloads] + ["data: [DONE]"]


def _run_stream(monkeypatch, lines, **kwargs):
    monkeypatch.setattr("mai.client.requests.post", lambda *a, **kw: _FakeResponse(lines))
    return list(_client().chat_completion_stream([{"role": "user", "content": "x"}], **kwargs))


def test_stream_assembles_parallel_tool_calls_without_index(monkeypatch):
    """MAI sends each tool call complete in its own chunk, with an id and no index."""
    lines = _sse(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "id": "a",
                                "type": "function",
                                "function": {
                                    "name": "get_region_capacity",
                                    "arguments": '{"region": "eastus"}',
                                },
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "id": "b",
                                "type": "function",
                                "function": {
                                    "name": "get_region_capacity",
                                    "arguments": '{"region": "westeurope"}',
                                },
                            }
                        ]
                    }
                }
            ]
        },
    )
    events = _run_stream(monkeypatch, lines)
    message = next(v for k, v in events if k == "message")
    calls = message["tool_calls"]
    assert len(calls) == 2, "each id must start a new tool call, not concatenate arguments"
    assert [json.loads(c["function"]["arguments"])["region"] for c in calls] == [
        "eastus",
        "westeurope",
    ]


def test_stream_still_handles_indexed_openai_fragments(monkeypatch):
    """The classic OpenAI shape (indexed, fragmented arguments) must keep working."""
    lines = _sse(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "id": "a", "function": {"name": "f", "arguments": '{"x":'}}
                        ]
                    }
                }
            ]
        },
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": " 1}"}}]}}]},
    )
    events = _run_stream(monkeypatch, lines)
    message = next(v for k, v in events if k == "message")
    assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {"x": 1}


def test_stream_raises_on_mid_stream_error_after_partial_content(monkeypatch):
    """A safety block can follow partial text; that must not look like success."""
    lines = _sse(
        {"choices": [{"delta": {"content": "Here is the plan"}}]},
        {"error": {"type": "SafetyBlockedError", "message": "blocked", "request_id": "req-1"}},
    )
    with pytest.raises(MAIStreamError) as excinfo:
        _run_stream(monkeypatch, lines)
    assert excinfo.value.error_type == "SafetyBlockedError"
    assert "req-1" in str(excinfo.value)


def test_stream_captures_reasoning_and_stats(monkeypatch):
    lines = _sse(
        {
            "id": "req-9",
            "usage": {"total_tokens": 42},
            "choices": [
                {
                    "delta": {"content": "ok", "reasoning": {"encrypted_content": "OPAQUE"}},
                    "finish_reason": "stop",
                }
            ],
        }
    )
    events = _run_stream(monkeypatch, lines, reasoning_display="encrypted")
    stats = next(v for k, v in events if k == "stats")
    message = next(v for k, v in events if k == "message")
    assert stats["finish_reason"] == "stop"
    assert stats["usage"]["total_tokens"] == 42
    # Opaque reasoning is carried on the message so it can be echoed back verbatim.
    assert message["reasoning"] == {"encrypted_content": "OPAQUE"}


# ── execution mode ──────────────────────────────────────────────────────────────
def _speech_client(strict: bool) -> MAIClient:
    return MAIClient(
        Config(
            speech_key="k",
            speech_region="eastus",
            execution_mode="strict" if strict else "demo",
        )
    )


def test_demo_mode_degrades_to_fallback(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("service exploded")

    monkeypatch.setattr("mai.client.requests.post", boom)
    result = _speech_client(strict=False).synthesize("hello")
    assert result.source == "fallback"
    assert "service exploded" in (result.error or "")


def test_strict_mode_raises_with_a_clean_traceback(monkeypatch):
    """Strict mode surfaces the real failure without a helper detour.

    Asserting only that the failing frame survives would not protect this: the
    previous ``_degrade()`` helper preserved it too. What the bare ``raise``
    buys is the absence of an extra hop through the helper, so the traceback
    reads caller -> requests.post -> boom and nothing else.
    """
    import traceback

    def boom(*a, **kw):
        raise RuntimeError("service exploded")

    monkeypatch.setattr("mai.client.requests.post", boom)

    try:
        _speech_client(strict=True).synthesize("hello")
    except RuntimeError as exc:
        assert "service exploded" in str(exc)
        names = [f.name for f in traceback.extract_tb(exc.__traceback__)]
        assert "boom" in names, names
        assert "_degrade" not in names, f"strict re-raise detoured through a helper: {names}"
        # synthesize appears once (the raise site), not twice as it would when an
        # inner helper re-raises back out through the caller.
        assert names.count("synthesize") == 1, names
    else:
        raise AssertionError("strict mode should have raised instead of degrading")


def test_strict_image_generation_raises_without_an_extra_frame(monkeypatch):
    """The retry loop must give up with a bare raise, like the other methods."""
    import traceback

    def boom(*a, **kw):
        raise RuntimeError("image service exploded")

    monkeypatch.setattr("mai.client.requests.post", boom)
    client = MAIClient(
        Config(
            image_endpoint="https://example.services.ai.azure.com",
            image_api_key="k",
            execution_mode="strict",
        )
    )
    try:
        client.generate_image("a red circle", 768, 768)
    except RuntimeError as exc:
        names = [f.name for f in traceback.extract_tb(exc.__traceback__)]
        assert "boom" in names, names
        # Re-raising a saved exception after the loop would list generate_image twice.
        assert names.count("generate_image") == 1, names
    else:
        raise AssertionError("strict mode should have raised instead of degrading")


def test_demo_image_generation_still_degrades(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("image service exploded")

    monkeypatch.setattr("mai.client.requests.post", boom)
    client = MAIClient(
        Config(
            image_endpoint="https://example.services.ai.azure.com",
            image_api_key="k",
            execution_mode="demo",
        )
    )
    result = client.generate_image("a red circle", 768, 768)
    assert result.source == "fallback"
    assert "image service exploded" in (result.error or "")
