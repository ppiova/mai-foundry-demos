"""Demo 4 (backup) — MAI-Voice-2 "One message, three personalities".

Same text, three deliveries: Neutral · Empathy · Excited — via SSML
`mstts:express-as` style + styledegree. Closes with an EN→ES switch (the
multilingual moment) without changing the flow.

Note: expressive styles are voice-dependent. `empathy` exists on es-ES-Marta and
the multilingual voices, not on en-US voices (which use excited/hopeful/softvoice).
The client validates the style against the voice and substitutes the closest one,
surfacing a note — a good teaching moment rather than an error.
"""

from __future__ import annotations

import streamlit as st

from mai import DEMO_VOICES, VOICE_PRESETS, VOICES, MAIClient

SAMPLE_EN = (
    "I found the problem with your order. The replacement has already been "
    "shipped and will arrive tomorrow."
)
SAMPLE_ES = "Encontré el problema con tu pedido. El reemplazo ya fue enviado y va a llegar mañana."


def _play(client: MAIClient, text: str, voice: str, style: str | None, degree: float, key: str):
    with st.spinner(f"Synthesizing ({style or 'neutral'})…"):
        res = client.synthesize(text, voice=voice, style=style, styledegree=degree)
    note = res.meta.get("style_note")
    st.markdown(
        f"**{res.badge}** · {style or 'neutral'} · {res.elapsed:.1f}s"
        + (f"  ·  ⚠️ {note}" if note else "")
    )
    if res.error:
        st.warning(f"Live call failed → offline TTS. Detail: {res.error}")
    if res.data:
        st.audio(res.data, format=res.meta.get("mime", "audio/mp3"))
    else:
        st.info(
            "No audio produced offline (install pyttsx3 for audible fallback). SSML below is still valid for LIVE."
        )
    with st.expander("SSML", expanded=False):
        st.code(res.meta.get("ssml", ""), language="xml")


def render(client: MAIClient) -> None:
    st.subheader("🗣️ MAI-Voice-2 — One message, three personalities")
    st.caption("Tone · emotion · pacing · style via SSML — plus an EN→ES switch.")

    st.info(
        f"Mode: **{'🟢 LIVE' if client.cfg.speech_ready else '🟡 FALLBACK (OS TTS if available)'}**  ·  "
        f"REST `cognitiveservices/v1`  ·  `mstts:express-as` + `styledegree`"
    )

    lang = st.radio(
        "Sample", ["English", "Español (cierre multilingüe)"], horizontal=True, key="v_lang"
    )
    default_text = SAMPLE_EN if lang == "English" else SAMPLE_ES
    default_voice = "en-US-Ethan:MAI-Voice-2" if lang == "English" else "es-ES-Marta:MAI-Voice-2"

    voice = st.selectbox(
        "Voice", DEMO_VOICES, index=DEMO_VOICES.index(default_voice), key="v_voice"
    )
    text = st.text_area("Text", value=default_text, height=90, key="v_text")
    degree = st.slider("styledegree", 0.5, 2.0, 1.3, 0.1, key="v_degree")

    supported = sorted(VOICES.get(voice, {}).get("styles", set()))
    st.caption(
        f"Styles supported by **{voice}**: " + (", ".join(f"`{s}`" for s in supported) or "—")
    )
    if "empathy" not in supported:
        st.caption(
            "💡 `empathy` isn't on this voice — try **es-ES-Marta:MAI-Voice-2** for a true empathy style."
        )

    st.markdown("**Three personalities**")
    cols = st.columns(len(VOICE_PRESETS))
    for col, (label, style, _deg) in zip(cols, VOICE_PRESETS, strict=True):
        if col.button(label, key=f"v_preset_{label}", width="stretch"):
            _play(client, text, voice, style, degree, key=label)

    st.divider()
    st.markdown("**Manual style**")
    m1, m2 = st.columns([2, 1])
    manual_style = m1.selectbox("style", ["(neutral)"] + supported, key="v_manual_style")
    if m2.button("▶ Speak", key="v_manual_run", width="stretch"):
        _play(
            client,
            text,
            voice,
            None if manual_style == "(neutral)" else manual_style,
            degree,
            key="manual",
        )
