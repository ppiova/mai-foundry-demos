"""Finale — MAI Multimodal Campaign Agent.

Speech → Reasoning → Image → Speech, end to end:
  1. MAI-Transcribe-1.5 turns a spoken brief into text.
  2. MAI-Thinking-1 produces a campaign name, tagline, creative brief,
     a hero-image prompt and a voice-over script (as JSON).
  3. MAI-Image-2.5 renders the hero visual.
  4. MAI-Voice-2 generates a ~15s expressive voice-over.

The point: not isolated models — one multimodal platform stack.
"""

from __future__ import annotations

import json
import re

import streamlit as st

from mai import MAIClient

DEFAULT_BRIEF = (
    "Create a launch campaign for a new sustainable smart backpack targeted at business travelers."
)

_BRIEF_SYSTEM = (
    "You are a senior creative director. Given a product brief, respond with ONLY a "
    "JSON object (no prose, no code fence) with keys: campaign_name, tagline, "
    "creative_brief (2-3 sentences), hero_image_prompt (a vivid prompt for an image "
    "model), voiceover_script (about 40 words, ~15 seconds, energetic)."
)


def generate_brief(client: MAIClient, brief_text: str) -> tuple[dict, str, str | None]:
    """Return (campaign_dict, source, error)."""
    if client.thinking_ready():
        try:
            resp = client.chat_completion(
                [
                    {"role": "system", "content": _BRIEF_SYSTEM},
                    {"role": "user", "content": brief_text},
                ],
                temperature=0.7,
            )
            content = resp["choices"][0]["message"].get("content") or ""
            return _parse_json(content), "live", None
        except Exception as exc:
            return _fallback_brief(brief_text), "fallback", str(exc)
    return _fallback_brief(brief_text), "fallback", None


REQUIRED_CAMPAIGN_FIELDS = (
    "campaign_name",
    "tagline",
    "creative_brief",
    "hero_image_prompt",
    "voiceover_script",
)


def _parse_json(text: str) -> dict:
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
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")
    missing = [f for f in REQUIRED_CAMPAIGN_FIELDS if not str(data.get(f, "")).strip()]
    if missing:
        raise ValueError(f"Campaign JSON missing required field(s): {', '.join(missing)}")
    return data


def _fallback_brief(brief_text: str) -> dict:
    # Pull a rough product phrase from the brief for a data-driven-feeling result.
    m = re.search(r"(?:for a |a )([^.,]+?)(?: targeted| for | aimed|\.|,|$)", brief_text, re.I)
    product = (m.group(1).strip() if m else "new product").rstrip(".")
    return {
        "campaign_name": "Carry Forward",
        "tagline": "Built for the road. Designed for tomorrow.",
        "creative_brief": (
            f"A launch campaign for {product}. Position sustainability and "
            "smart utility as effortless, not preachy. Speak to frequent "
            "business travelers who value design, durability and low footprint."
        ),
        "hero_image_prompt": (
            f"Hero product shot of {product}, minimalist studio lighting, "
            "recycled materials visible, airport lounge bokeh background, "
            "premium eco branding, 16:9 negative space on the right"
        ),
        "voiceover_script": (
            "Meet the backpack that keeps up with you and the planet. "
            "Smart, sustainable, and built for the way you travel. "
            "Carry forward — your journey, reimagined."
        ),
    }


def _stage(label: str, source: str, elapsed: float, error: str | None = None):
    badge = "🟢 LIVE" if source == "live" else "🟡 FALLBACK"
    st.markdown(f"**{label}** — {badge} · {elapsed:.1f}s" + (f"  ·  ⚠️ {error}" if error else ""))


def render(client: MAIClient) -> None:
    st.subheader("🚀 Finale — MAI Multimodal Campaign Agent")
    st.caption("Speech → Reasoning → Image → Speech, in one flow.")

    st.info(
        "Chains **Transcribe-1.5 → Thinking-1 → Image-2.5 → Voice-2**. Each stage badges LIVE/FALLBACK."
    )

    brief_text = st.text_area("Spoken/typed brief", value=DEFAULT_BRIEF, height=80, key="mm_brief")
    c1, c2 = st.columns(2)
    if c1.button("🔊 Speak this brief (TTS) & use as audio", key="mm_tts"):
        tts = client.synthesize(brief_text, voice="en-US-Ethan:MAI-Voice-2")
        if tts.data:
            st.session_state["mm_audio"] = tts.data
            st.session_state["mm_audio_mime"] = tts.meta.get("mime", "audio/mp3")
    up = c2.file_uploader("…or upload a spoken brief", type=["wav", "mp3", "flac"], key="mm_up")
    if up is not None:
        st.session_state["mm_audio"] = up.read()
        st.session_state["mm_audio_mime"] = up.type or "audio/wav"
    audio = st.session_state.get("mm_audio")
    if audio:
        st.audio(audio, format=st.session_state.get("mm_audio_mime", "audio/mp3"))

    if st.button("▶ Run full campaign", type="primary", key="mm_run"):
        total = 0.0

        # 1) Speech → text
        st.markdown("### 1 · Speech → text")
        if audio:
            tr = client.transcribe(audio, phrases=["backpack", "sustainable"], locales=["en"])
            _stage("MAI-Transcribe-1.5", tr.source, tr.elapsed, tr.error)
            total += tr.elapsed
            brief_used = tr.data
            st.write(brief_used)
        else:
            brief_used = brief_text
            st.caption("No audio provided — using typed brief.")

        # 2) Reasoning → campaign
        st.markdown("### 2 · Reasoning → campaign")
        import time

        t0 = time.time()
        campaign, src, err = generate_brief(client, brief_used)
        el = time.time() - t0
        _stage("MAI-Thinking-1", src, el, err)
        total += el
        st.markdown(f"**{campaign.get('campaign_name', '')}** — *{campaign.get('tagline', '')}*")
        st.write(campaign.get("creative_brief", ""))

        # 3) Image → hero
        st.markdown("### 3 · Image → hero visual")
        img = client.generate_image(
            campaign.get("hero_image_prompt", brief_used), width=1024, height=768
        )
        _stage(img.meta.get("model", "MAI-Image"), img.source, img.elapsed, img.error)
        total += img.elapsed
        st.image(img.data, width="stretch", caption=campaign.get("hero_image_prompt", ""))

        # 4) Speech → voice-over
        st.markdown("### 4 · Voice-over")
        vo = client.synthesize(
            campaign.get("voiceover_script", ""),
            voice="en-US-Harper:MAI-Voice-2",
            style="excited",
            styledegree=1.3,
        )
        _stage("MAI-Voice-2", vo.source, vo.elapsed, vo.error)
        total += vo.elapsed
        if vo.data:
            st.audio(vo.data, format=vo.meta.get("mime", "audio/mp3"))
        st.write(campaign.get("voiceover_script", ""))

        st.success(f"End-to-end multimodal pipeline complete · total {total:.1f}s")
