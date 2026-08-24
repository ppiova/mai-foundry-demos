"""MAI demos — shared client library."""

from .client import MAIClient, MAIResult
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
    "Config",
    "get_config",
    "build_ssml",
    "resolve_style",
    "VOICES",
    "DEMO_VOICES",
    "VOICE_PRESETS",
]
