"""MAIClient — one pluggable client for all four MAI model families.

Design goals (per the presentation requirement "must not fail live on stage"):

* If credentials are configured, call the REAL API exactly as documented in
  docs/API_VERIFIED.md.
* If they're not configured, OR the live call raises for any reason, degrade to
  a deterministic FALLBACK and keep going.
* Every result carries ``source`` ("live" | "fallback") so the UI can badge it.

Only ``requests`` is used for HTTP so the code matches the Microsoft REST docs
line-for-line and has no SDK version coupling.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from . import fallback
from .config import Config, get_config
from .ssml import build_ssml


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

    def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Raw OpenAI-compatible chat completion against MAI-Thinking-1.

        Raises on any HTTP error (the caller decides whether to fall back).
        """
        payload: dict[str, Any] = {
            "model": self.cfg.thinking_deployment,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        resp = requests.post(
            self.cfg.chat_url,
            headers={"Content-Type": "application/json", "api-key": self.cfg.foundry_api_key},
            json=payload,
            timeout=self.cfg.request_timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def chat_completion_stream(
        self, messages: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto"
    ):
        """Stream an OpenAI-compatible chat completion (SSE).

        Yields ``("content", delta)`` for each text delta and finally
        ``("message", assembled_message)`` once, where the assembled message has
        standard ``content`` / ``tool_calls`` fields ready to append and execute.
        Raises on HTTP error (caller decides whether to fall back).
        """
        payload: dict[str, Any] = {
            "model": self.cfg.thinking_deployment,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        content_parts: list[str] = []
        tool_acc: list[dict] = []  # ordered, assembled tool calls
        index_map: dict[int, int] = {}  # streamed index -> position in tool_acc
        with requests.post(
            self.cfg.chat_url,
            headers={"Content-Type": "application/json", "api-key": self.cfg.foundry_api_key},
            json=payload,
            timeout=self.cfg.request_timeout,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8")
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
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
        if tool_acc:
            message["tool_calls"] = [
                {
                    "id": s["id"] or f"call_{i}",
                    "type": "function",
                    "function": {"name": s["name"], "arguments": s["args"] or "{}"},
                }
                for i, s in enumerate(tool_acc)
            ]
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
                    timeout=self.cfg.request_timeout,
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
                png = fallback.edit_image(image_bytes, prompt)
                return MAIResult(
                    "fallback", png, {"prompt": prompt}, error=str(exc), elapsed=time.time() - t0
                )
        png = fallback.edit_image(image_bytes, prompt)
        return MAIResult("fallback", png, {"prompt": prompt}, elapsed=time.time() - t0)

    # ── Image generation (text-to-image; also powers the Flash "speed" demo) ─────
    def generate_image(
        self, prompt: str, width: int = 1024, height: int = 1024, deployment: str | None = None
    ) -> MAIResult:
        """Generate an image from a text prompt.

        On a live error, walk a short fallback ladder before giving up to the
        deterministic mock: retry at 768x768 (handles size limits), then retry on the
        base ``MAI-Image-2.5`` deployment (handles a missing/unavailable deployment).
        """
        t0 = time.time()
        deployment = deployment or self.cfg.image_gen_deployment
        if self.cfg.image_ready:
            attempts = [
                {"model": deployment, "prompt": prompt, "width": width, "height": height},
            ]
            if max(width, height) > 768:
                attempts.append(
                    {"model": deployment, "prompt": prompt, "width": 768, "height": 768}
                )
            if deployment != "MAI-Image-2.5":
                attempts.append(
                    {"model": "MAI-Image-2.5", "prompt": prompt, "width": 768, "height": 768}
                )

            last_error: Exception | None = None
            for payload in attempts:
                try:
                    resp = requests.post(
                        self.cfg.image_url("generations"),
                        headers={
                            "Content-Type": "application/json",
                            "api-key": self.cfg.image_api_key,
                        },
                        json=payload,
                        timeout=self.cfg.request_timeout,
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
                    if payload is attempts[-1]:
                        break
                    if not _is_retryable_image_error(exc):
                        break

            png = fallback.generate_image(prompt, width, height)
            return MAIResult(
                "fallback",
                png,
                {"prompt": prompt, "model": deployment},
                error=str(last_error or "image request failed"),
                elapsed=time.time() - t0,
            )

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
    ) -> MAIResult:
        t0 = time.time()
        definition: dict[str, Any] = {
            "enhancedMode": {"enabled": True, "model": self.cfg.transcribe_model}
        }
        if locales:
            definition["locales"] = locales
        if verbatim:
            definition["enhancedMode"]["transcribeStyle"] = "verbatim"
        if phrases:
            definition["phraseList"] = {"phrases": phrases}

        if self.cfg.transcribe_ready and audio_bytes:
            try:
                resp = requests.post(
                    self.cfg.transcribe_url,
                    headers={"Ocp-Apim-Subscription-Key": self.cfg.speech_key},
                    files={"audio": (filename, audio_bytes, "application/octet-stream")},
                    data={"definition": json.dumps(definition)},
                    timeout=self.cfg.request_timeout,
                )
                resp.raise_for_status()
                text = _extract_transcript(resp.json())
                return MAIResult(
                    "live",
                    text,
                    {"phrases": phrases or [], "verbatim": verbatim, "definition": definition},
                    elapsed=time.time() - t0,
                )
            except Exception as exc:
                text = fallback.transcribe(phrases, verbatim)
                return MAIResult(
                    "fallback",
                    text,
                    {"phrases": phrases or [], "verbatim": verbatim},
                    error=str(exc),
                    elapsed=time.time() - t0,
                )
        text = fallback.transcribe(phrases, verbatim)
        return MAIResult(
            "fallback",
            text,
            {"phrases": phrases or [], "verbatim": verbatim},
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
                    timeout=self.cfg.request_timeout,
                )
                resp.raise_for_status()
                meta["mime"] = "audio/mp3"
                return MAIResult("live", resp.content, meta, elapsed=time.time() - t0)
            except Exception as exc:
                audio, mime = fallback.synthesize(text)
                meta["mime"] = mime
                return MAIResult("fallback", audio, meta, error=str(exc), elapsed=time.time() - t0)
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
    raise ValueError(f"No b64_json in image response: {str(payload)[:200]}")


def _is_retryable_image_error(exc: Exception) -> bool:
    """Whether to try the next image attempt. Because each retry *changes* the request
    (smaller size / base model), 400/404 are treated as retryable here — not just
    transient 5xx/429."""
    if isinstance(exc, requests.Timeout):
        return True
    if isinstance(exc, requests.HTTPError):
        status = getattr(exc.response, "status_code", None)
        return status in {400, 404, 429, 500, 502, 503, 504}
    return True


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
    return json.dumps(payload)[:500]
