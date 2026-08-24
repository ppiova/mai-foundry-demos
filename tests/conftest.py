"""Pytest configuration.

Forces FALLBACK mode for the whole session (no credentials, fully offline) so the
suite runs anywhere, including CI, without touching the real MAI APIs. Setting the
env vars here — before any test imports ``mai`` — means ``load_dotenv`` (which never
overrides existing values) leaves them empty even if a local ``.env`` exists.
"""

import os
import sys
from pathlib import Path

for _key in (
    "MAI_FOUNDRY_ENDPOINT",
    "MAI_FOUNDRY_API_KEY",
    "MAI_IMAGE_ENDPOINT",
    "MAI_IMAGE_API_KEY",
    "MAI_SPEECH_ENDPOINT",
    "MAI_SPEECH_KEY",
):
    os.environ[_key] = ""

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
