"""Central configuration + model/voice registries for the MAI demos.

Everything is driven by environment variables (see .env.example). Nothing here
requires credentials to import — with no keys the app runs in FALLBACK mode.

The voice registry and style data come straight from docs/API_VERIFIED.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


@dataclass(frozen=True)
class Config:
    # Foundry (Thinking-1 + Image-2.5)
    foundry_endpoint: str = field(default_factory=lambda: _env("MAI_FOUNDRY_ENDPOINT").rstrip("/"))
    foundry_api_key: str = field(default_factory=lambda: _env("MAI_FOUNDRY_API_KEY"))
    thinking_deployment: str = field(
        default_factory=lambda: _env("MAI_THINKING_DEPLOYMENT", "MAI-Thinking-1")
    )
    image_edit_deployment: str = field(
        default_factory=lambda: _env("MAI_IMAGE_EDIT_DEPLOYMENT", "MAI-Image-2.5")
    )
    image_gen_deployment: str = field(
        default_factory=lambda: _env("MAI_IMAGE_GEN_DEPLOYMENT", "MAI-Image-2.5-Flash")
    )

    # Image models may live on a SEPARATE resource (e.g. when the chat/Foundry
    # resource is in a region that doesn't offer MAI image models). Set these to a
    # Foundry resource in a supported region to turn Image LIVE; leave blank to keep
    # Image in fallback. (If image is on the same resource as chat, set these to the
    # same values as MAI_FOUNDRY_ENDPOINT / MAI_FOUNDRY_API_KEY.)
    image_endpoint: str = field(default_factory=lambda: _env("MAI_IMAGE_ENDPOINT").rstrip("/"))
    image_api_key: str = field(default_factory=lambda: _env("MAI_IMAGE_API_KEY"))

    # Speech (Transcribe-1.5 + Voice-2)
    speech_endpoint: str = field(default_factory=lambda: _env("MAI_SPEECH_ENDPOINT").rstrip("/"))
    speech_key: str = field(default_factory=lambda: _env("MAI_SPEECH_KEY"))
    speech_region: str = field(default_factory=lambda: _env("MAI_SPEECH_REGION", "eastus"))
    transcribe_model: str = field(
        default_factory=lambda: _env("MAI_TRANSCRIBE_MODEL", "mai-transcribe-1.5")
    )
    transcribe_api_version: str = field(
        default_factory=lambda: _env("MAI_TRANSCRIBE_API_VERSION", "2025-10-15")
    )

    # Per-service (connect, read) timeouts. Reasoning legitimately streams for
    # 30-150s, so a single short budget would abort healthy runs. Keep each API
    # independently tunable: a slow transcription must not also lengthen TTS.
    thinking_connect_timeout: int = field(
        default_factory=lambda: int(_env("MAI_THINKING_CONNECT_TIMEOUT", "10"))
    )
    thinking_read_timeout: int = field(
        default_factory=lambda: int(_env("MAI_THINKING_READ_TIMEOUT", "300"))
    )
    image_connect_timeout: int = field(
        default_factory=lambda: int(_env("MAI_IMAGE_CONNECT_TIMEOUT", "10"))
    )
    image_read_timeout: int = field(
        default_factory=lambda: int(_env("MAI_IMAGE_READ_TIMEOUT", "180"))
    )
    transcribe_connect_timeout: int = field(
        default_factory=lambda: int(_env("MAI_TRANSCRIBE_CONNECT_TIMEOUT", "10"))
    )
    transcribe_read_timeout: int = field(
        default_factory=lambda: int(_env("MAI_TRANSCRIBE_READ_TIMEOUT", "180"))
    )
    voice_connect_timeout: int = field(
        default_factory=lambda: int(_env("MAI_VOICE_CONNECT_TIMEOUT", "10"))
    )
    voice_read_timeout: int = field(
        default_factory=lambda: int(_env("MAI_VOICE_READ_TIMEOUT", "90"))
    )

    # "demo" (default): a failed live call degrades to a labelled fallback so a
    # stage demo never dies. "strict": live failures raise, so pre-flight checks
    # and CI can actually fail. See MAI_EXECUTION_MODE in .env.example.
    execution_mode: str = field(default_factory=lambda: _env("MAI_EXECUTION_MODE", "demo").lower())

    def __post_init__(self) -> None:
        normalized = self.execution_mode.strip().lower()
        object.__setattr__(self, "execution_mode", normalized)
        if normalized not in {"demo", "strict"}:
            raise ValueError("MAI_EXECUTION_MODE must be 'demo' or 'strict'")

    # ── timeouts / execution mode ────────────────────────────────────────────
    @property
    def strict(self) -> bool:
        """True when live failures must raise instead of degrading to fallback."""
        return self.execution_mode == "strict"

    @property
    def thinking_timeout(self) -> tuple[int, int]:
        return (self.thinking_connect_timeout, self.thinking_read_timeout)

    @property
    def image_timeout(self) -> tuple[int, int]:
        return (self.image_connect_timeout, self.image_read_timeout)

    @property
    def transcribe_timeout(self) -> tuple[int, int]:
        return (self.transcribe_connect_timeout, self.transcribe_read_timeout)

    @property
    def voice_timeout(self) -> tuple[int, int]:
        return (self.voice_connect_timeout, self.voice_read_timeout)

    # ── readiness flags ──────────────────────────────────────────────────────
    @property
    def foundry_ready(self) -> bool:
        return bool(self.foundry_endpoint and self.foundry_api_key)

    @property
    def image_ready(self) -> bool:
        return bool(self.image_endpoint and self.image_api_key)

    @property
    def speech_ready(self) -> bool:
        return bool(self.speech_key and self.speech_region)

    @property
    def transcribe_ready(self) -> bool:
        return bool(self.speech_endpoint and self.speech_key)

    @property
    def any_service_ready(self) -> bool:
        """Credential readiness without importing or depending on Streamlit."""
        return self.foundry_ready or self.image_ready or self.speech_ready or self.transcribe_ready

    # ── derived URLs ─────────────────────────────────────────────────────────
    @property
    def chat_url(self) -> str:
        """Native MAI chat-completions surface.

        This is the path in the current MAI-Thinking-1 Microsoft Learn article;
        see docs/API_VERIFIED.md.
        """
        return f"{self.foundry_endpoint}/mai/v1/chat/completions"

    def image_url(self, kind: str) -> str:
        # kind in {"edits", "generations"}
        return f"{self.image_endpoint}/mai/v1/images/{kind}"

    @property
    def transcribe_url(self) -> str:
        return (
            f"{self.speech_endpoint}/speechtotext/transcriptions:transcribe"
            f"?api-version={self.transcribe_api_version}"
        )

    @property
    def tts_url(self) -> str:
        return f"https://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()


# ─────────────────────────────────────────────────────────────────────────────
# Voice registry — voice name -> supported mstts:express-as styles.
# Source: docs/API_VERIFIED.md (Microsoft Learn, verified 2026-08-25).
# ─────────────────────────────────────────────────────────────────────────────
_EN_RICH = {
    "angry",
    "confused",
    "determined",
    "disgusted",
    "embarrassed",
    "excited",
    "fearful",
    "happy",
    "hopeful",
    "jealous",
    "joyful",
    "regretful",
    "relieved",
    "sad",
    "shouting",
    "softvoice",
    "surprised",
    "whispering",
}
_HARPER = {
    "angry",
    "confused",
    "determined",
    "embarrassed",
    "excited",
    "happy",
    "hopeful",
    "joyful",
    "regretful",
    "relieved",
    "sad",
    "shouting",
    "softvoice",
    "whispering",
}
_EMPATHIC = {
    "adventurous",
    "caring",
    "empathy",
    "curious",
    "encouraging",
    "excited",
    "friendly",
    "cheerful",
    "nostalgic",
    "reflective",
    "sad",
    "disappointed",
    "serious",
}

VOICES: dict[str, dict] = {
    "en-US-Ethan:MAI-Voice-2": {"locale": "en-US", "gender": "M", "styles": set(_EN_RICH)},
    "en-US-Harper:MAI-Voice-2": {"locale": "en-US", "gender": "F", "styles": set(_HARPER)},
    "en-US-Olivia:MAI-Voice-2": {"locale": "en-US", "gender": "F", "styles": set(_EN_RICH)},
    "es-ES-Marta:MAI-Voice-2": {"locale": "es-ES", "gender": "F", "styles": set(_EMPATHIC)},
    "es-MX-Valeria:MAI-Voice-2": {"locale": "es-MX", "gender": "F", "styles": set(_EN_RICH)},
    "es-MX-Alejo:MAI-Voice-2": {"locale": "es-MX", "gender": "M", "styles": set(_EN_RICH)},
}

# Order shown in dropdowns.
DEMO_VOICES = list(VOICES.keys())

# Three-personalities presets: (label, desired_style_or_None, styledegree)
VOICE_PRESETS = [
    ("Neutral", None, 1.0),
    ("Empathy", "empathy", 1.3),
    ("Excited", "excited", 1.5),
]

# When a voice lacks the desired style, try these in order (closest first).
STYLE_FALLBACKS: dict[str, list[str]] = {
    "empathy": ["caring", "hopeful", "softvoice", "friendly", "cheerful"],
    "excited": ["happy", "joyful", "cheerful", "hopeful"],
    "cheerful": ["happy", "joyful", "friendly"],
    "sad": ["regretful", "disappointed", "reflective"],
}


def resolve_style(voice: str, desired: str | None) -> tuple[str | None, str | None]:
    """Return (style_to_use, note). ``note`` is set when a substitution happened.

    Guarantees the returned style is actually supported by ``voice`` so we never
    send an SSML the service will reject.
    """
    if desired is None:
        return None, None
    supported = VOICES.get(voice, {}).get("styles", set())
    if desired in supported:
        return desired, None
    for alt in STYLE_FALLBACKS.get(desired, []):
        if alt in supported:
            return alt, f"'{desired}' isn't supported by {voice}; using '{alt}'."
    return None, f"'{desired}' isn't supported by {voice}; using a neutral style."
