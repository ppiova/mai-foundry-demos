"""Finale — MAI Multimodal Campaign Agent.

Speech → Reasoning → Image → Speech, end to end:
  1. MAI-Transcribe-1.5 turns a spoken brief into text.
  2. MAI-Thinking-1 produces a campaign name, tagline, creative brief,
     a hero-image prompt and a voice-over script (as JSON).
  3. The configured MAI Image deployment renders the hero visual.
  4. MAI-Voice-2 generates a ~15s expressive voice-over.

The point: not isolated models — one multimodal platform stack.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import streamlit as st

from mai import MAIClient

from . import _notices as notices
from ._audio import AudioInput, sync_upload

DEFAULT_BRIEF = (
    "Create a launch campaign for a new sustainable smart backpack targeted at business travelers."
)

_BRIEF_SYSTEM = (
    "You are a senior creative director. Given a product brief, respond with ONLY a "
    "JSON object (no prose, no code fence) with keys: campaign_name, tagline, "
    "creative_brief (2-3 sentences), hero_image_prompt (a vivid prompt for an image "
    "model), voiceover_script (about 40 words, ~15 seconds, energetic)."
)


@dataclass(frozen=True)
class Campaign:
    campaign_name: str
    tagline: str
    creative_brief: str
    hero_image_prompt: str
    voiceover_script: str

    @classmethod
    def from_mapping(cls, data: object) -> Campaign:
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object, got {type(data).__name__}")
        missing = [
            field
            for field in REQUIRED_CAMPAIGN_FIELDS
            if not isinstance(data.get(field), str) or not data[field].strip()
        ]
        if missing:
            raise ValueError(f"Campaign JSON missing required field(s): {', '.join(missing)}")
        return cls(**{field: data[field].strip() for field in REQUIRED_CAMPAIGN_FIELDS})


def generate_brief(client: MAIClient, brief_text: str) -> tuple[Campaign, str, str | None]:
    """Return (campaign_dict, source, error)."""
    if client.thinking_ready():
        try:
            resp = client.chat_completion(
                [
                    {"role": "system", "content": _BRIEF_SYSTEM},
                    {"role": "user", "content": brief_text},
                ],
                # The budget includes reasoning tokens as well as the short JSON.
                max_completion_tokens=8192,
            )
            content = resp["choices"][0]["message"].get("content") or ""
            return _parse_json(content), "live", None
        except Exception as exc:
            if client.cfg.strict:
                raise
            return _fallback_brief(brief_text), "fallback", str(exc)
    if client.cfg.strict:
        raise RuntimeError("Thinking service is not configured")
    return _fallback_brief(brief_text), "fallback", None


REQUIRED_CAMPAIGN_FIELDS = (
    "campaign_name",
    "tagline",
    "creative_brief",
    "hero_image_prompt",
    "voiceover_script",
)


def _parse_json(text: str) -> Campaign:
    """Parse the campaign JSON and require every field the pipeline depends on.

    A partially-filled object would silently produce an empty hero prompt or a
    blank voice-over, so an incomplete response raises and degrades to the
    deterministic fallback brief instead.
    """
    text = text.strip()
    if "```" in text:
        text = re.sub(r"```(json)?", "", text).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    data = json.loads(m.group(0) if m else text)
    return Campaign.from_mapping(data)


def _fallback_brief(brief_text: str) -> Campaign:
    # Pull a rough product phrase from the brief for a data-driven-feeling result.
    m = re.search(r"(?:for a |a )([^.,]+?)(?: targeted| for | aimed|\.|,|$)", brief_text, re.I)
    product = (m.group(1).strip() if m else "new product").rstrip(".")
    return Campaign(
        campaign_name="Carry Forward",
        tagline="Built for the road. Designed for tomorrow.",
        creative_brief=(
            f"A launch campaign for {product}. Position sustainability and "
            "smart utility as effortless, not preachy. Speak to frequent "
            "business travelers who value design, durability and low footprint."
        ),
        hero_image_prompt=(
            f"Hero product shot of {product}, minimalist studio lighting, "
            "recycled materials visible, airport lounge bokeh background, "
            "premium eco branding, landscape composition, negative space on the right"
        ),
        voiceover_script=(
            "Meet the backpack that keeps up with you and the planet. "
            "Smart, sustainable, and built for the way you travel. "
            "Carry forward — your journey, reimagined."
        ),
    )


def _stage(label: str, source: str, elapsed: float, error: str | None = None):
    badge = "🟢 LIVE" if source == "live" else "🟡 FALLBACK"
    st.markdown(f"**{label}** — {badge} · {elapsed:.1f}s" + (f"  ·  ⚠️ {error}" if error else ""))


def render(client: MAIClient) -> None:
    st.subheader("🚀 Finale — MAI Multimodal Campaign Agent")
    st.caption("Speech → Reasoning → Image → Speech, in one flow.")

    st.info(
        "Chains "
        f"**Transcribe-1.5 → Thinking-1 → `{client.cfg.image_gen_deployment}` → Voice-2**. "
        "Each stage badges LIVE/FALLBACK."
    )

    brief_text = st.text_area("Spoken/typed brief", value=DEFAULT_BRIEF, height=80, key="mm_brief")
    if st.session_state.get("mm_tts_text", brief_text) != brief_text:
        st.session_state["mm_tts_audio"] = None
        st.session_state["mm_tts_text"] = brief_text
        if st.session_state.get("mm_source") == "tts":
            st.session_state["mm_source"] = "text"
            st.info(
                "The brief changed — using the current typed text. Generate TTS again to hear it."
            )

    c1, c2 = st.columns(2)
    up = c2.file_uploader("…or upload a spoken brief", type=["wav", "mp3", "flac"], key="mm_up")
    upload_audio = sync_upload("mm", up, removed_source="text")
    if c1.button("🔊 Speak this brief (TTS) & use as audio", key="mm_tts"):
        st.session_state["mm_tts_audio"] = None
        st.session_state["mm_source"] = "tts"
        tts = client.synthesize(brief_text, voice="en-US-Ethan:MAI-Voice-2")
        st.session_state["mm_tts_audio"] = AudioInput.from_tts(tts, "brief")
        st.session_state["mm_tts_text"] = brief_text
        if not tts.data:
            st.warning(
                "No TTS audio was produced. Generate it again, select Typed brief, or upload audio."
            )
    notices.audio_consent()
    source = st.radio(
        "Active brief source",
        ["text", "tts", "upload"],
        format_func={
            "text": "Typed brief",
            "tts": "Generated speech (TTS)",
            "upload": "Uploaded audio",
        }.get,
        horizontal=True,
        key="mm_source",
        help="New uploads and TTS generation select that source. Removing an active upload returns to typed text.",
    )
    audio = {"upload": upload_audio, "tts": st.session_state.get("mm_tts_audio")}.get(source)
    if audio and audio.data:
        st.audio(audio.data, format=audio.mime)
        if source == "tts":
            notices.synthetic_voice()

    if st.button("▶ Run full campaign", type="primary", key="mm_run"):
        if source != "text" and (audio is None or not audio.data):
            st.error(
                "The selected source needs non-empty audio. Generate TTS, upload a file, or select Typed brief."
            )
            return
        total = 0.0

        # 1) Speech → text
        st.markdown("### 1 · Speech → text")
        if audio:
            tr = client.transcribe(
                audio.data,
                filename=audio.filename,
                mime=audio.mime,
                phrases=["backpack", "sustainable"],
                locales=["en"],
            )
            _stage("MAI-Transcribe-1.5", tr.source, tr.elapsed, tr.error)
            total += tr.elapsed
            brief_used = tr.data
            st.write(brief_used)
        else:
            brief_used = brief_text
            st.caption("Typed brief selected — using the current text without transcription.")

        # 2) Reasoning → campaign
        st.markdown("### 2 · Reasoning → campaign")
        import time

        t0 = time.time()
        campaign, src, err = generate_brief(client, brief_used)
        el = time.time() - t0
        _stage("MAI-Thinking-1", src, el, err)
        total += el
        st.markdown(f"**{campaign.campaign_name}** — *{campaign.tagline}*")
        st.write(campaign.creative_brief)

        # 3) Image → hero
        st.markdown("### 3 · Image → hero visual")
        img = client.generate_image(campaign.hero_image_prompt, width=1024, height=768)
        _stage(img.meta.get("model", "MAI-Image"), img.source, img.elapsed, img.error)
        total += img.elapsed
        st.image(img.data, width="stretch", caption=campaign.hero_image_prompt)

        # 4) Speech → voice-over
        st.markdown("### 4 · Voice-over")
        vo = client.synthesize(
            campaign.voiceover_script,
            voice="en-US-Harper:MAI-Voice-2",
            style="excited",
            styledegree=1.3,
        )
        _stage("MAI-Voice-2", vo.source, vo.elapsed, vo.error)
        total += vo.elapsed
        if vo.data:
            st.audio(vo.data, format=vo.meta.get("mime", "audio/mp3"))
            notices.synthetic_voice()
        st.write(campaign.voiceover_script)

        st.success(f"End-to-end multimodal pipeline complete · total {total:.1f}s")
