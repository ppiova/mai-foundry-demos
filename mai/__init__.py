"""MAI demos — shared client library."""

from .client import MAIClient, MAIResult, audio_extension_for_mime
from .config import (
    DEMO_VOICES,
    VOICE_PRESETS,
    VOICES,
    Config,
    get_config,
    resolve_style,
)
from .ssml import build_ssml

__all__ = [
    "MAIClient",
    "MAIResult",
    "audio_extension_for_mime",
    "Config",
    "get_config",
    "build_ssml",
    "resolve_style",
    "VOICES",
    "DEMO_VOICES",
    "VOICE_PRESETS",
]
