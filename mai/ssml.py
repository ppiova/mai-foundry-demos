"""SSML construction for MAI-Voice-2, with style validation.

Kept tiny and dependency-free so the Voice demo and the multimodal finale can
share exactly one SSML builder.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from .config import VOICES, resolve_style

_SPEAK_OPEN = (
    "<speak version='1.0' "
    "xmlns='http://www.w3.org/2001/10/synthesis' "
    "xmlns:mstts='http://www.w3.org/2001/mstts' "
    "xml:lang='{lang}'>"
)


def build_ssml(
    text: str,
    voice: str = "en-US-Ethan:MAI-Voice-2",
    style: str | None = None,
    styledegree: float | None = None,
) -> tuple[str, str | None]:
    """Return ``(ssml, note)``.

    ``note`` is non-None when the requested style was substituted because the
    chosen voice doesn't support it (see :func:`mai.config.resolve_style`).
    """
    lang = VOICES.get(voice, {}).get("locale", "en-US")
    used_style, note = resolve_style(voice, style)
    inner = escape(text.strip())

    if used_style:
        degree_attr = f" styledegree='{styledegree:g}'" if styledegree else ""
        inner = f"<mstts:express-as style='{used_style}'{degree_attr}>{inner}</mstts:express-as>"

    ssml = _SPEAK_OPEN.format(lang=lang) + f"<voice name='{voice}'>{inner}</voice>" + "</speak>"
    return ssml, note
