"""Audio inputs and source transitions shared by the two speech demos."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from mai import MAIResult, audio_extension_for_mime


@dataclass(frozen=True)
class AudioInput:
    data: bytes
    filename: str
    mime: str

    @classmethod
    def from_tts(cls, result: MAIResult, stem: str) -> AudioInput | None:
        if not result.data:
            return None
        mime = result.meta.get("mime") or "audio/mp3"
        return cls(result.data, stem + audio_extension_for_mime(mime), mime)


def sync_upload(prefix: str, uploaded, *, removed_source: str = "upload") -> AudioInput | None:
    """Activate changed uploads, not unchanged uploads on every widget rerun.

    Clearing the uploader clears its stored bytes. Transcribe stays on an empty
    upload until the user chooses TTS; Campaign returns to the current typed brief.
    """
    key = f"{prefix}_upload_audio"
    upload_id = uploaded.file_id if uploaded is not None else None
    id_key = f"{prefix}_upload_id"
    if upload_id != st.session_state.get(id_key):
        audio = (
            AudioInput(uploaded.getvalue(), uploaded.name, uploaded.type or "audio/wav")
            if uploaded is not None
            else None
        )
        st.session_state[key] = audio
        st.session_state[id_key] = upload_id
        if audio is not None:
            st.session_state[f"{prefix}_source"] = "upload"
        elif st.session_state.get(f"{prefix}_source") == "upload":
            st.session_state[f"{prefix}_source"] = removed_source
    return st.session_state.get(key)
