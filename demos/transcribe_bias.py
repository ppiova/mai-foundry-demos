"""Demo 3 — MAI-Transcribe-1.5 entity biasing (phraseList).

Same audio, transcribed twice: plain vs. with a domain `phraseList`. The hard
proper nouns (Fabrikam XQ-17, KEDA, Dapr, Rehaan, …) are recovered on the right.
Optional `verbatim` toggle preserves fillers/disfluencies.
"""

from __future__ import annotations

import html
import re

import streamlit as st

from mai import MAIClient, audio_extension_for_mime
from mai.fallback import ENTITIES, SAMPLE_TRANSCRIPT_SCRIPT


def _highlight(text: str, phrases: list[str]) -> str:
    out = html.escape(text)
    for p in sorted(phrases, key=len, reverse=True):
        out = re.sub(
            re.escape(html.escape(p)),
            lambda m: (
                f"<mark style='background:#c8f7c5;border-radius:3px;padding:0 3px'>{m.group(0)}</mark>"
            ),
            out,
            flags=re.IGNORECASE,
        )
    return f"<div style='line-height:1.7;font-size:1.02rem'>{out}</div>"


def render(client: MAIClient) -> None:
    st.subheader("🎙️ MAI-Transcribe-1.5 — Entity biasing")
    st.caption("Names, brands, industrial terminology — recovered with a domain phraseList.")

    live = client.cfg.transcribe_ready
    st.info(
        f"Mode: **{'🟢 LIVE' if live else '🟡 FALLBACK (simulated)'}**  ·  "
        f"model `{client.cfg.transcribe_model}`  ·  `phraseList` + `transcribeStyle`"
    )

    st.markdown("**Spoken script**")
    st.code(SAMPLE_TRANSCRIPT_SCRIPT, language=None)
    st.markdown("**Domain phraseList:** " + ", ".join(f"`{e}`" for e in ENTITIES))

    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    verbatim = c3.toggle(
        "verbatim", value=False, key="tr_verbatim", help="Preserve filler words and disfluencies."
    )

    # --- get audio (needed for a live call; optional for fallback) ---
    if c1.button("🔊 Generate sample audio (TTS)", key="tr_gen"):
        with st.spinner("Synthesizing sample audio…"):
            tts = client.synthesize(SAMPLE_TRANSCRIPT_SCRIPT, voice="en-US-Ethan:MAI-Voice-2")
        if tts.data:
            st.session_state["tr_audio"] = tts.data
            st.session_state["tr_audio_mime"] = tts.meta.get("mime", "audio/mp3")
            st.session_state["tr_audio_name"] = "sample" + audio_extension_for_mime(
                st.session_state["tr_audio_mime"]
            )
        else:
            st.warning(
                "No offline TTS audio was produced (install pyttsx3), so upload a non-empty WAV, MP3, or FLAC file to continue."
            )
    up = c2.file_uploader(
        "…or upload audio (WAV/MP3/FLAC)", type=["wav", "mp3", "flac"], key="tr_up"
    )
    if up is not None:
        st.session_state["tr_audio"] = up.read()
        st.session_state["tr_audio_mime"] = up.type or "audio/wav"
        st.session_state["tr_audio_name"] = up.name

    audio = st.session_state.get("tr_audio")
    if audio:
        st.audio(audio, format=st.session_state.get("tr_audio_mime", "audio/mp3"))

    if st.button("▶ Transcribe: baseline vs phraseList", type="primary", key="tr_run"):
        if not audio:
            st.error(
                "Transcription needs non-empty audio. Click **Generate sample audio** or upload a file."
            )
            return
        name = st.session_state.get("tr_audio_name", "audio.wav")
        with st.spinner("Transcribing twice…"):
            base = client.transcribe(
                audio or b"",
                filename=name,
                mime=st.session_state.get("tr_audio_mime"),
                phrases=None,
                verbatim=verbatim,
                locales=["en"],
            )
            biased = client.transcribe(
                audio or b"",
                filename=name,
                mime=st.session_state.get("tr_audio_mime"),
                phrases=ENTITIES,
                verbatim=verbatim,
                locales=["en"],
            )
        st.markdown(
            f"**{base.badge}**  ·  baseline {base.elapsed:.1f}s · biased {biased.elapsed:.1f}s"
        )
        if base.error or biased.error:
            st.warning(f"Live call failed → simulated. Detail: {base.error or biased.error}")
        left, right = st.columns(2)
        left.markdown("**Baseline** (no phraseList)")
        left.markdown(_highlight(base.data, ENTITIES), unsafe_allow_html=True)
        right.markdown("**With phraseList** (entity biasing)")
        right.markdown(_highlight(biased.data, ENTITIES), unsafe_allow_html=True)
        st.success(
            "Green = domain entities. Note how the baseline mangles the proper nouns the phraseList recovers."
        )
