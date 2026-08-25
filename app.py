"""MAI Examples — a Streamlit app of short, focused demos for the MAI stack.

Run:  streamlit run app.py
Each demo proves exactly one claim from the deck and runs LIVE (with keys in .env)
or in FALLBACK mode (no keys), degrading per-call if a live request fails.
"""

from __future__ import annotations

# Load .env FIRST, before any mai imports
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

import streamlit as st

from demos import (
    image_edit,
    image_speed,
    multimodal_campaign,
    thinking_agent,
    transcribe_bias,
    voice_personalities,
)
from mai import MAIClient, get_config

st.set_page_config(page_title="MAI Examples", page_icon="🧩", layout="wide")


@st.cache_resource
def get_client() -> MAIClient:
    return MAIClient()


def _status_row(label: str, ready: bool, detail: str):
    st.markdown(f"{'🟢' if ready else '🟡'} **{label}** — {'LIVE' if ready else 'FALLBACK'}")
    st.caption(detail)


def sidebar(cfg):
    with st.sidebar:
        st.title("🧩 MAI Examples")
        st.caption(
            "Short demos for the MAI multimodal stack. Verified API surface: `docs/API_VERIFIED.md`."
        )
        st.divider()
        st.markdown("### Service status")
        _status_row(
            "Thinking-1",
            cfg.foundry_ready,
            f"Foundry endpoint {'set' if cfg.foundry_endpoint else 'missing'} · deploy `{cfg.thinking_deployment}`",
        )
        _status_row(
            "Image-2.5 / Flash",
            cfg.image_ready,
            "dedicated image endpoint set"
            if cfg.image_endpoint
            else "set MAI_IMAGE_ENDPOINT to a supported-region resource",
        )
        _status_row(
            "Transcribe-1.5",
            cfg.transcribe_ready,
            f"Speech endpoint {'set' if cfg.speech_endpoint else 'missing'} · `{cfg.transcribe_model}`",
        )
        _status_row(
            "Voice-2 (TTS)",
            cfg.speech_ready,
            f"Region `{cfg.speech_region}` · key {'set' if cfg.speech_key else 'missing'}",
        )
        st.divider()
        if not cfg.any_service_ready:
            st.info(
                "No keys detected — running fully in **FALLBACK** mode. Copy `.env.example` to `.env` and add keys to go LIVE."
            )
        st.caption("Tip: rehearse in fallback, then flip keys on for the live run.")


def main():
    cfg = get_config()
    client = get_client()
    sidebar(cfg)

    st.title("MAI Examples")
    st.caption(
        "Reasoning · controlled image editing · domain transcription · expressive voice — and a multimodal finale."
    )

    tabs = st.tabs(
        [
            "🧠 Thinking · Decision Agent",
            "🎨 Image-2.5 · Surgical Edit",
            "🎙️ Transcribe · Entity biasing",
            "🚀 Finale · Multimodal",
            "— backup —",
            "🗣️ Voice-2 · Personalities",
            "⚡ Image-Flash · Speed",
        ]
    )

    with tabs[0]:
        thinking_agent.render(client)
    with tabs[1]:
        image_edit.render(client)
    with tabs[2]:
        transcribe_bias.render(client)
    with tabs[3]:
        multimodal_campaign.render(client)
    with tabs[4]:
        st.markdown("### Backup demos")
        st.caption("Kept aside for the 30–45 min flow; here if you want them.")
    with tabs[5]:
        voice_personalities.render(client)
    with tabs[6]:
        image_speed.render(client)


if __name__ == "__main__":
    main()
