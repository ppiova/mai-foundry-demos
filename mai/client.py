"""MAIClient — one pluggable client for all four MAI model families.

Design goals (per the presentation requirement "must not fail live on stage"):

* If credentials are configured, call the REAL API exactly as documented in
  docs/API_VERIFIED.md.
* In default ``demo`` mode, missing credentials or a live failure degrade to a
  deterministic FALLBACK. In ``strict`` mode they raise.
* Every result carries ``source`` ("live" | "fallback") so the UI can badge it.

Only ``requests`` is used for HTTP so the code matches the Microsoft REST docs
line-for-line and has no SDK version coupling.
"""

from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from . import fallback
from .config import Config, get_config
from .ssml import build_ssml


class MAIStreamError(RuntimeError):
    """An error delivered *inside* an SSE stream rather than as an HTTP status.

    MAI can start streaming content and only then refuse (e.g. a safety block),
    emitting a ``{"error": {...}}`` event followed by ``[DONE]``. Without this,
    the partial text would look like a successful, complete answer.
    """

    def __init__(self, error_type: str, message: str, request_id: str | None = None):
        self.error_type = error_type
        self.message = message
        self.request_id = request_id
        detail = f"{error_type}: {message}"
        if request_id:
            detail += f" (request_id={request_id})"
        super().__init__(detail)


@dataclass
class MAIResult:
    source: str  # "live" | "fallback"
    data: Any = None  # str | bytes | dict, depends on call
    meta: dict = field(default_factory=dict)
    error: str | None = None  # populated when a live call fell back
    elapsed: float = 0.0

    @property
    def is_live(self) -> bool:
        return self.source == "live"

    @property
    def badge(self) -> str:
        return "🟢 LIVE" if self.is_live else "🟡 FALLBACK"


class MAIClient:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or get_config()

    # ── Thinking-1 (raw chat; the tool loop lives in demos/thinking_agent.py) ──
    def thinking_ready(self) -> bool:
        return self.cfg.foundry_ready

    def _chat_payload(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        max_completion_tokens: int | None,
        reasoning_display: str | None,
    ) -> dict[str, Any]:
        """Build a MAI-Thinking-1 request body.

        Parameter support verified against a live deployment (docs/API_VERIFIED.md):
        ``max_tokens`` is rejected with 400 ("use `max_completion_tokens` instead"),
        and ``reasoning_display`` is only accepted on the native /mai/v1/ path.
        Optional arguments are omitted entirely rather than sent as null.
        """
        payload: dict[str, Any] = {
            "model": self.cfg.thinking_deployment,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        if max_completion_tokens is not None:
            payload["max_completion_tokens"] = max_completion_tokens
        if reasoning_display is not None:
            payload["reasoning_display"] = reasoning_display
        return payload

    def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_completion_tokens: int | None = None,
        reasoning_display: str | None = None,
    ) -> dict:
        """Non-streaming chat completion against MAI-Thinking-1.

        Raises on any HTTP error (the caller decides whether to fall back).
        """
        if not self.cfg.foundry_ready:
            raise RuntimeError("Thinking service is not configured")
        resp = requests.post(
            self.cfg.chat_url,
            headers={"Content-Type": "application/json", "api-key": self.cfg.foundry_api_key},
            json=self._chat_payload(messages, tools, max_completion_tokens, reasoning_display),
            timeout=self.cfg.thinking_timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def chat_completion_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_completion_tokens: int | None = None,
        reasoning_display: str | None = None,
    ):
        """Stream a chat completion (SSE) from MAI-Thinking-1.

        Yields ``("content", delta)`` per text delta, then exactly one
        ``("message", assembled_message)``. The assembled message carries
        ``content`` / ``tool_calls`` ready to execute, plus, when
        ``reasoning_display="encrypted"`` was requested, an opaque ``reasoning``
        blob. Append that message back verbatim on the next round so the model
        keeps its reasoning state across tool calls — never render or log it.

        Raises ``MAIStreamError`` if the service reports an error mid-stream (a
        safety block can arrive *after* partial content) so truncated output is
        never mistaken for a complete answer.
        """
        if not self.cfg.foundry_ready:
            raise RuntimeError("Thinking service is not configured")
        payload = self._chat_payload(messages, tools, max_completion_tokens, reasoning_display)
        payload["stream"] = True

        content_parts: list[str] = []
        tool_acc: list[dict] = []  # ordered, assembled tool calls
        index_map: dict[int, int] = {}  # streamed index -> position in tool_acc
        assistant_fields: dict[str, Any] = {}
        stats: dict[str, Any] = {}
        event_type: str | None = None
        with requests.post(
            self.cfg.chat_url,
            headers={"Content-Type": "application/json", "api-key": self.cfg.foundry_api_key},
            json=payload,
            timeout=self.cfg.thinking_timeout,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8")
                if line.startswith("event:"):
                    event_type = line[6:].strip().lower()
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    if event_type == "error":
                        raise MAIStreamError("SSEError", "Streaming request failed") from None
                    continue
                if not isinstance(chunk, dict):
                    if event_type == "error":
                        raise MAIStreamError("SSEError", "Streaming request failed")
                    continue

                # An error event can follow partial content (e.g. a safety block).
                # Surface it instead of returning the truncated text as success.
                err = chunk.get("error")
                if err or event_type == "error" or chunk.get("type") == "error":
                    err = err if isinstance(err, dict) else chunk
                    raise MAIStreamError(
                        err.get("type") or err.get("code") or "UnknownError",
                        err.get("message", "Streaming request failed"),
                        err.get("request_id") or chunk.get("id"),
                    )
                event_type = None

                # Observability: usage/model/id arrive at the top level of chunks.
                for key in ("usage", "model", "system_fingerprint", "created", "object"):
                    if chunk.get(key) is not None:
                        stats[key] = chunk[key]
                if chunk.get("id"):
                    stats.setdefault("request_id", chunk["id"])

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                if choice.get("finish_reason"):
                    stats["finish_reason"] = choice["finish_reason"]
                    if choice["finish_reason"] in {"blocked", "content_filter", "safety"}:
                        raise MAIStreamError(
                            "SafetyBlockedError", "Streaming response was blocked by safety filters"
                        )
                delta = choice.get("delta") or {}
                for key in ("reasoning", "refusal", "annotations"):
                    if delta.get(key) is not None:
                        assistant_fields[key] = delta[key]
                if delta.get("content"):
                    content_parts.append(delta["content"])
                    yield ("content", delta["content"])
                for tc in delta.get("tool_calls") or []:
                    slot = _tc_slot(tc, tool_acc, index_map)
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["args"] += fn["arguments"]

        message: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts) or None}
        message.update(assistant_fields)
        if tool_acc:
            message["tool_calls"] = [
                {
                    # Never invent a service tool-call id: the follow-up must refer
                    # to the actual opaque id or reject the malformed call.
                    "id": s["id"],
                    "type": "function",
                    "function": {"name": s["name"], "arguments": s["args"] or "{}"},
                }
                for s in tool_acc
            ]
        # Opaque reasoning state — echoed back untouched, never displayed.
        if stats:
            yield ("stats", stats)
        yield ("message", message)

    # ── Image-2.5 edit ─────────────────────────────────────────────────────────
    def edit_image(
        self, image_bytes: bytes, prompt: str, filename: str = "input.png", mime: str = "image/png"
    ) -> MAIResult:
        t0 = time.time()
        if self.cfg.image_ready:
            try:
                resp = requests.post(
                    self.cfg.image_url("edits"),
                    headers={"api-key": self.cfg.image_api_key},
                    data={"model": self.cfg.image_edit_deployment, "prompt": prompt},
                    files={"image": (filename, image_bytes, mime)},
                    timeout=self.cfg.image_timeout,
                )
                resp.raise_for_status()
                png = _first_b64_png(resp.json())
                return MAIResult(
                    "live",
                    png,
                    {"prompt": prompt, "model": self.cfg.image_edit_deployment},
                    elapsed=time.time() - t0,
                )
            except Exception as exc:  # degrade
                if self.cfg.strict:
                    raise
                png = fallback.edit_image(image_bytes, prompt)
                return MAIResult(
                    "fallback",
                    png,
                    {"prompt": prompt, "model": self.cfg.image_edit_deployment},
                    error=str(exc),
                    elapsed=time.time() - t0,
                )
        if self.cfg.strict:
            raise RuntimeError("Image service is not configured")
        png = fallback.edit_image(image_bytes, prompt)
        return MAIResult(
            "fallback",
            png,
            {"prompt": prompt, "model": self.cfg.image_edit_deployment},
            elapsed=time.time() - t0,
        )

    # ── Image generation (text-to-image; also powers the Flash "speed" demo) ─────
    def generate_image(
        self, prompt: str, width: int = 1024, height: int = 1024, deployment: str | None = None
    ) -> MAIResult:
        """Generate an image from a text prompt.

        On a live error, walk a short fallback ladder before giving up to the
        deterministic mock: retry at 768x768 (handles size limits), then retry on the
        base edit deployment (handles a missing/unavailable deployment).
        """
        t0 = time.time()
        deployment = deployment or self.cfg.image_gen_deployment
        if self.cfg.image_ready:
            attempts = [{"model": deployment, "prompt": prompt, "width": width, "height": height}]
            seen: set[tuple[str, int, int]] = set()
            last_error: Exception | None = None
            while attempts:
                payload = attempts.pop(0)
                key = (payload["model"], payload["width"], payload["height"])
                if key in seen:
                    continue
                seen.add(key)
                try:
                    resp = requests.post(
                        self.cfg.image_url("generations"),
                        headers={
                            "Content-Type": "application/json",
                            "api-key": self.cfg.image_api_key,
                        },
                        json=payload,
                        timeout=self.cfg.image_timeout,
                    )
                    resp.raise_for_status()
                    png = _first_b64_png(resp.json())
                    return MAIResult(
                        "live",
                        png,
                        {"prompt": prompt, "model": payload["model"]},
                        elapsed=time.time() - t0,
                    )
                except Exception as exc:
                    last_error = exc
                    retry = _next_image_attempt(exc, payload, self.cfg.image_edit_deployment)
                    if retry and (retry["model"], retry["width"], retry["height"]) not in seen:
                        attempts.append(retry)
                        continue
                    # Give up. Raising here (bare, inside the except block) keeps
                    # the traceback free of an extra re-raise frame.
                    if self.cfg.strict:
                        raise
                    break
            png = fallback.generate_image(prompt, width, height)
            return MAIResult(
                "fallback",
                png,
                {"prompt": prompt, "model": deployment},
                error=str(last_error or "image request failed"),
                elapsed=time.time() - t0,
            )

        if self.cfg.strict:
            raise RuntimeError("Image service is not configured")
        png = fallback.generate_image(prompt, width, height)
        return MAIResult(
            "fallback", png, {"prompt": prompt, "model": deployment}, elapsed=time.time() - t0
        )

    # ── Transcribe-1.5 ──────────────────────────────────────────────────────────
    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        phrases: list[str] | None = None,
        verbatim: bool = False,
        locales: list[str] | None = None,
        mime: str | None = None,
    ) -> MAIResult:
        t0 = time.time()
        audio_mime = _validate_audio(audio_bytes, filename, mime)
        definition: dict[str, Any] = {
            "enhancedMode": {"enabled": True, "model": self.cfg.transcribe_model}
        }
        if locales:
            definition["locales"] = locales
        if verbatim:
            definition["enhancedMode"]["transcribeStyle"] = "verbatim"
        if phrases:
            definition["phraseList"] = {"phrases": phrases}

        if self.cfg.transcribe_ready:
            try:
                resp = requests.post(
                    self.cfg.transcribe_url,
                    headers={"Ocp-Apim-Subscription-Key": self.cfg.speech_key},
                    files={"audio": (filename, audio_bytes, audio_mime)},
                    data={"definition": json.dumps(definition)},
                    timeout=self.cfg.transcribe_timeout,
                )
                resp.raise_for_status()
                text = _extract_transcript(resp.json())
                return MAIResult(
                    "live",
                    text,
                    {
                        "phrases": phrases or [],
                        "verbatim": verbatim,
                        "definition": definition,
                        "mime": audio_mime,
                    },
                    elapsed=time.time() - t0,
                )
            except Exception as exc:
                if self.cfg.strict:
                    raise
                text = fallback.transcribe(phrases, verbatim)
                return MAIResult(
                    "fallback",
                    text,
                    {"phrases": phrases or [], "verbatim": verbatim, "mime": audio_mime},
                    error=str(exc),
                    elapsed=time.time() - t0,
                )
        if self.cfg.strict:
            raise RuntimeError("Transcription service is not configured")
        text = fallback.transcribe(phrases, verbatim)
        return MAIResult(
            "fallback",
            text,
            {"phrases": phrases or [], "verbatim": verbatim, "mime": audio_mime},
            elapsed=time.time() - t0,
        )

    # ── Voice-2 ─────────────────────────────────────────────────────────────────
    def synthesize(
        self,
        text: str,
        voice: str = "en-US-Ethan:MAI-Voice-2",
        style: str | None = None,
        styledegree: float | None = None,
    ) -> MAIResult:
        t0 = time.time()
        ssml, note = build_ssml(text, voice=voice, style=style, styledegree=styledegree)
        meta = {"voice": voice, "style": style, "ssml": ssml, "style_note": note}

        if self.cfg.speech_ready:
            try:
                resp = requests.post(
                    self.cfg.tts_url,
                    headers={
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": "audio-24khz-160kbitrate-mono-mp3",
                        "Ocp-Apim-Subscription-Key": self.cfg.speech_key,
                    },
                    data=ssml.encode("utf-8"),
                    timeout=self.cfg.voice_timeout,
                )
                resp.raise_for_status()
                meta["mime"] = "audio/mpeg"
                return MAIResult("live", resp.content, meta, elapsed=time.time() - t0)
            except Exception as exc:
                if self.cfg.strict:
                    raise
                audio, mime = fallback.synthesize(text)
                meta["mime"] = mime
                return MAIResult("fallback", audio, meta, error=str(exc), elapsed=time.time() - t0)
        if self.cfg.strict:
            raise RuntimeError("Voice service is not configured")
        audio, mime = fallback.synthesize(text)
        meta["mime"] = mime
        return MAIResult("fallback", audio, meta, elapsed=time.time() - t0)


# ── response parsing helpers ────────────────────────────────────────────────────
def _tc_slot(tc: dict, tool_acc: list[dict], index_map: dict[int, int]) -> dict:
    """Pick the accumulation slot for a streamed tool_call delta.

    Handles both streaming styles:
    * indexed fragments (standard OpenAI): keyed by ``index``;
    * complete-per-chunk without ``index`` (MAI-Thinking-1 on Foundry): each
      delta carrying an ``id`` starts a new tool call.
    """
    idx = tc.get("index")
    if idx is not None:
        if idx not in index_map:
            index_map[idx] = len(tool_acc)
            tool_acc.append({"id": None, "name": "", "args": ""})
        return tool_acc[index_map[idx]]
    if tc.get("id") or not tool_acc:
        tool_acc.append({"id": None, "name": "", "args": ""})
    return tool_acc[-1]


def _first_b64_png(payload: dict) -> bytes:
    import base64

    for item in payload.get("data", []):
        if "b64_json" in item:
            return base64.b64decode(item["b64_json"])
    raise ValueError("Image response did not contain PNG data")


def _next_image_attempt(exc: Exception, payload: dict, fallback_deployment: str) -> dict | None:
    """Return one meaningfully changed retry, or stop for transient/unrelated errors."""
    if not isinstance(exc, requests.HTTPError):
        return None
    status = getattr(exc.response, "status_code", None)
    retry = dict(payload)
    if status in {400, 413, 422} and (payload["width"], payload["height"]) != (768, 768):
        retry.update(width=768, height=768)
        return retry
    if status in {400, 404} and payload["model"] != fallback_deployment:
        retry["model"] = fallback_deployment
        return retry
    return None


def _extract_transcript(payload: dict) -> str:
    """Fast-transcription responses vary a little; parse defensively."""
    if isinstance(payload, dict):
        combined = payload.get("combinedPhrases")
        if isinstance(combined, list) and combined:
            joined = " ".join(c.get("text", "") for c in combined).strip()
            if joined:
                return joined
        phrases = payload.get("phrases")
        if isinstance(phrases, list) and phrases:
            joined = " ".join(p.get("text", p.get("displayText", "")) for p in phrases).strip()
            if joined:
                return joined
        for key in ("displayText", "text"):
            if payload.get(key):
                return str(payload[key])
    # Never hand back raw JSON as if it were a transcript.
    raise ValueError("Transcription response did not contain recognizable transcript text")


_AUDIO_MIME = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
}


def _audio_mime(filename: str) -> str:
    """Best-effort MIME from the file extension (Speech accepts WAV/MP3/FLAC)."""
    ext = pathlib.Path(filename).suffix.lower()
    return _AUDIO_MIME.get(ext, "application/octet-stream")


_SUPPORTED_AUDIO_MIMES = {
    "audio/flac",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-flac",
    "audio/x-wav",
}


def _validate_audio(audio_bytes: bytes, filename: str, mime: str | None) -> str:
    if not audio_bytes:
        raise ValueError("Audio input is empty")
    supplied = (mime or "").split(";", 1)[0].strip().lower()
    inferred = _audio_mime(filename)
    if supplied in _SUPPORTED_AUDIO_MIMES:
        return supplied
    if inferred in _SUPPORTED_AUDIO_MIMES:
        # Browsers sometimes report application/octet-stream. The supported file
        # extension is more useful and must be the MIME sent to Speech.
        return inferred
    raise ValueError("Unsupported audio format; use WAV, MP3, or FLAC")


_AUDIO_EXTENSION_BY_MIME = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
}


def audio_extension_for_mime(mime: str | None) -> str:
    """Return a filename extension that matches actual audio metadata."""
    normalized = (mime or "").split(";", 1)[0].strip().lower()
    return _AUDIO_EXTENSION_BY_MIME.get(normalized, ".bin")
