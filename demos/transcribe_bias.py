"""Demo 3 — MAI-Transcribe-1.5 entity biasing (phraseList).

Same audio, transcribed twice: plain vs. with a domain `phraseList`. The hard
proper nouns (Fabrikam XQ-17, KEDA, Dapr, Rehaan, …) are recovered on the right.
The `verbatim` toggle illustrates fillers/disfluencies only in fallback;
mai-transcribe-1.5 is always verbatim live.
"""

from __future__ import annotations

import html
import re

import streamlit as st

from mai import MAIClient
from mai.fallback import ENTITIES, SAMPLE_TRANSCRIPT_SCRIPT

from . import _notices as notices
from ._audio import AudioInput, sync_upload


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
        f"Service: **{'configured for LIVE' if live else 'FALLBACK (simulated)'}**  ·  "
        f"model `{client.cfg.transcribe_model}`  ·  `phraseList` + `transcribeStyle`"
    )

    st.markdown("**Spoken script**")
    st.code(SAMPLE_TRANSCRIPT_SCRIPT, language=None)
    st.markdown("**Domain phraseList:** " + ", ".join(f"`{e}`" for e in ENTITIES))

    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    verbatim = c3.toggle(
        "verbatim", value=False, key="tr_verbatim", help="Preserve filler words and disfluencies."
    )
    # Verified live (2026-09-11, docs/API_VERIFIED.md section 3): mai-transcribe-1.5
    # already defaults to verbatim, and rejects "clean" outright (HTTP 400). This
    # model has no other style to switch to, so the toggle above has no effect on
    # a live call: say so rather than let it imply a change that will not happen.
    c3.caption("mai-transcribe-1.5 is always verbatim; this has no effect live.")

    up = c2.file_uploader(
        "…or upload audio (WAV/MP3/FLAC)", type=["wav", "mp3", "flac"], key="tr_up"
    )
    upload_audio = sync_upload("tr", up)
    if c1.button("🔊 Generate sample audio (TTS)", key="tr_gen"):
        st.session_state["tr_tts_audio"] = None
        st.session_state["tr_source"] = "tts"
        with st.spinner("Synthesizing sample audio…"):
            tts = client.synthesize(SAMPLE_TRANSCRIPT_SCRIPT, voice="en-US-Ethan:MAI-Voice-2")
        st.session_state["tr_tts_audio"] = AudioInput.from_tts(tts, "sample")
        if not tts.data:
            st.warning(
                "No offline TTS audio was produced (install pyttsx3), so upload a non-empty WAV, MP3, or FLAC file to continue."
            )
    notices.audio_consent()
    source = st.radio(
        "Active audio source",
        ["tts", "upload"],
        format_func={"tts": "Generated sample (TTS)", "upload": "Uploaded audio"}.get,
        horizontal=True,
        key="tr_source",
        help="New uploads and TTS generation select that source; reruns keep your choice.",
    )
    audio = upload_audio if source == "upload" else st.session_state.get("tr_tts_audio")
    if audio and audio.data:
        st.audio(audio.data, format=audio.mime)
        if source == "tts":
            notices.synthetic_voice()

    if st.button("▶ Transcribe: baseline vs phraseList", type="primary", key="tr_run"):
        if audio is None or not audio.data:
            st.error(
                "The selected source needs non-empty audio. Click **Generate sample audio**, upload a file, or select an available source."
            )
            return
        with st.spinner("Transcribing twice…"):
            base = client.transcribe(
                audio.data,
                filename=audio.filename,
                mime=audio.mime,
                phrases=None,
                verbatim=verbatim,
                locales=["en"],
            )
            biased = client.transcribe(
                audio.data,
                filename=audio.filename,
                mime=audio.mime,
                phrases=ENTITIES,
                verbatim=verbatim,
                locales=["en"],
            )
        mixed = base.is_live != biased.is_live
        if mixed:
            status = "🟠 MIXED — LIVE + FALLBACK"
        else:
            status = "🟢 LIVE" if base.is_live else "🟡 FALLBACK (simulated)"
        st.markdown(f"**Comparison: {status}**")
        for col, label, result in zip(
            st.columns(2),
            ("Baseline (no phraseList)", "With phraseList (entity biasing)"),
            (base, biased),
            strict=True,
        ):
            with col:
                st.markdown(f"**{label}**")
                st.markdown(f"**{result.badge}** · {result.elapsed:.1f}s")
                if result.error:
                    st.warning(f"Live call failed → simulated. Detail: {result.error}")
                if not result.is_live:
                    st.info(
                        "Simulated transcript: a canned string from the offline fallback, "
                        "not measured from this audio."
                    )
                st.markdown(_highlight(result.data, ENTITIES), unsafe_allow_html=True)
        if mixed:
            st.warning(
                "Mixed provenance: one transcript is live and the other is simulated. "
                "This comparison cannot measure the effect of phraseList."
            )
        if base.is_live and biased.is_live:
            st.success(
                "Green = domain entities. Compare the two live transcripts to assess the effect of phraseList."
            )
