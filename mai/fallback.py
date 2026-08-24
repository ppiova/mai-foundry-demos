"""Deterministic offline stand-ins for each MAI model.

These exist so the app runs with zero credentials (rehearsal) and so a live call
that fails on stage degrades to *something* instead of an error. They are clearly
labelled as mock output in the UI — never presented as real model results.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# ─────────────────────────────────────────────────────────────────────────────
# Shared reference script for the Transcribe demo. The asset builder can turn
# this into sample audio, and the fallback transcript is derived from it so the
# entity-biasing before/after is consistent.
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_TRANSCRIPT_SCRIPT = (
    "Yesterday the Fabrikam XQ-17 team deployed KEDA and Dapr on AKS. "
    "The incident was escalated to Rehaan and Jessie, and we tracked it in the "
    "MAI-Thinking-1 workspace before rolling back."
)

# Domain entities the plain model tends to mangle; phraseList fixes them.
ENTITIES = ["Fabrikam XQ-17", "KEDA", "Dapr", "AKS", "Rehaan", "Jessie", "MAI-Thinking-1"]

# What a generic model hears without entity biasing (plausible errors).
_BASELINE_ERRORS = (
    "Yesterday the fabric am X Q seventeen team deployed Kedah and dapper on A K S. "
    "The incident was escalated to Rehan and Jesse, and we tracked it in the "
    "my thinking one workspace before rolling back."
)

_VERBATIM_FILLERS = (
    "Um, yesterday the Fabrikam XQ-17 team, uh, deployed KEDA and Dapr on AKS. "
    "The incident was, like, escalated to Rehaan and Jessie, and we, um, tracked it "
    "in the MAI-Thinking-1 workspace before rolling back."
)


def transcribe(phrases: list[str] | None, verbatim: bool) -> str:
    """Simulate the entity-biasing effect from the known reference script."""
    if phrases:  # phraseList supplied -> proper nouns recovered
        return _VERBATIM_FILLERS if verbatim else SAMPLE_TRANSCRIPT_SCRIPT
    # No phraseList -> baseline mangles the hard entities.
    if verbatim:
        return "Um, " + _BASELINE_ERRORS.replace("Yesterday", "yesterday", 1)
    return _BASELINE_ERRORS


# ─────────────────────────────────────────────────────────────────────────────
# Image fallbacks (procedural, deterministic).
# ─────────────────────────────────────────────────────────────────────────────
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _ribbon(img: Image.Image, text: str) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    f = _font(max(14, img.width // 45))
    pad = 8
    tw = draw.textlength(text, font=f)
    draw.rectangle([0, 0, tw + 2 * pad, f.size + 2 * pad], fill=(0, 0, 0, 150))
    draw.text((pad, pad), text, fill=(255, 220, 120), font=f)


def edit_image(image_bytes: bytes, prompt: str) -> bytes:
    """Warm 'sunset' grade + banner as a visible stand-in for a real edit."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size

    # Warm sunset wash.
    grad = Image.new("RGB", (w, h))
    gpx = grad.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(255 * (0.95 - 0.15 * t))
        g = int(150 + 40 * (1 - t))
        b = int(90 + 120 * t)
        for x in range(w):
            gpx[x, y] = (r, g, b)
    img = Image.blend(img, grad, 0.35)
    img = ImageEnhance.Contrast(img).enhance(1.05)

    _ribbon(img, "FALLBACK · mock edit (no live API)")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> bytes:
    """A simple studio-product mock whose palette varies with the prompt."""
    width = max(256, min(width, 1024))
    height = max(256, min(height, 1024))
    seed = int(hashlib.md5(prompt.encode("utf-8")).hexdigest(), 16)

    palettes = [
        ((238, 242, 247), (60, 72, 96)),
        ((250, 244, 236), (120, 70, 50)),
        ((235, 247, 240), (40, 100, 80)),
        ((245, 236, 247), (90, 50, 110)),
        ((236, 244, 250), (30, 80, 130)),
        ((250, 240, 240), (130, 50, 60)),
    ]
    bg, accent = palettes[seed % len(palettes)]

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    # Soft floor.
    draw.rectangle([0, int(height * 0.68), width, height], fill=tuple(max(0, c - 18) for c in bg))
    # Product silhouette (rounded bottle/mug).
    cx, cw, ch = width // 2, width // 5, int(height * 0.42)
    top = int(height * 0.24)
    draw.rounded_rectangle([cx - cw, top, cx + cw, top + ch], radius=cw // 2, fill=accent)
    draw.ellipse(
        [cx - cw // 2, top - cw // 3, cx + cw // 2, top + cw // 3],
        fill=tuple(min(255, c + 30) for c in accent),
    )
    # Label band.
    draw.rectangle(
        [cx - cw, top + ch // 3, cx + cw, top + ch // 3 + ch // 5],
        fill=tuple(min(255, c + 60) for c in accent),
    )

    f = _font(max(14, width // 40))
    draw.text(
        (16, height - 30),
        (prompt[:70] + "…") if len(prompt) > 70 else prompt,
        fill=(90, 90, 90),
        font=f,
    )
    _ribbon(img, "FALLBACK · mock generation")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Voice fallback: OS TTS via pyttsx3 if available; otherwise no audio (UI shows SSML).
# ─────────────────────────────────────────────────────────────────────────────
def synthesize(text: str) -> tuple[bytes | None, str]:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        tmp = Path(tempfile.gettempdir()) / "mai_fallback_tts.wav"
        engine.save_to_file(text, str(tmp))
        engine.runAndWait()
        if tmp.exists() and tmp.stat().st_size > 0:
            data = tmp.read_bytes()
            with contextlib.suppress(Exception):
                tmp.unlink()
            return data, "audio/wav"
    except Exception:
        pass
    return None, "none"
