"""MAI Examples — a Streamlit app of short, focused demos for the MAI stack.

Run:  streamlit run app.py
Each demo illustrates one focused capability and runs LIVE (endpoints in .env,
plus an Entra identity or a key) or in FALLBACK mode, degrading per-call if a
live request fails.
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
    # "configured" rather than "working": readiness is a check on what is set,
    # not a token acquisition (mai/auth.py deliberately makes no network call at
    # import). Only the badge on an actual result can say a call went live.
    state = "configured for LIVE" if ready else "FALLBACK"
    st.markdown(f"{'🟢' if ready else '🟡'} **{label}** · {state}")
    st.caption(detail)


def _auth_detail(keyless: bool, key: str) -> str:
    """How this service will authenticate, given what is configured."""
    if keyless:
        return "Entra ID"
    return "resource key" if key else "no credential"


def sidebar(cfg, client=None):
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
            f"Endpoint {'set' if cfg.foundry_endpoint else 'missing'}"
            f" · {_auth_detail(cfg.keyless_enabled, cfg.foundry_api_key)}"
            f" · deploy `{cfg.thinking_deployment}`",
        )
        _status_row(
            "Image-2.5 / Flash",
            cfg.image_ready,
            f"Dedicated image endpoint set · {_auth_detail(cfg.keyless_enabled, cfg.image_api_key)}"
            if cfg.image_endpoint
            else "Set MAI_IMAGE_ENDPOINT to a supported-region resource",
        )
        _status_row(
            "Transcribe-1.5",
            cfg.transcribe_ready,
            f"Speech endpoint {'set' if cfg.speech_endpoint else 'missing'}"
            f" · {_auth_detail(cfg.transcribe_keyless, cfg.speech_key)}"
            f" · `{cfg.transcribe_model}`",
        )
        # Voice is the one service whose keyless path needs more than an endpoint,
        # so say which prerequisite is missing rather than just reporting FALLBACK.
        if cfg.voice_keyless:
            voice_detail = "Resource endpoint · Entra ID + resource ID"
        elif cfg.speech_key:
            voice_detail = f"Region `{cfg.speech_region}` · resource key"
        elif cfg.keyless_enabled:
            voice_detail = "Keyless TTS also needs MAI_SPEECH_RESOURCE_ID"
        else:
            voice_detail = "No credential"
        _status_row("Voice-2 (TTS)", cfg.speech_ready, voice_detail)
        st.divider()
        if not cfg.any_service_ready:
            hint = (
                "Copy `.env.example` to `.env`, add the endpoints, and run `az login`."
                if cfg.keyless_enabled
                else "Copy `.env.example` to `.env` and add the endpoints and keys."
            )
            st.info(f"Nothing configured, so every demo runs in **FALLBACK** mode. {hint}")
        # A token that failed to resolve is covered by a configured key, which keeps
        # the demo alive but means the run is no longer keyless. Say so: believing
        # you are exercising Entra when you are not is how the keyless path ships
        # unverified.
        if client is not None and getattr(client, "auth_fallback", None):
            st.warning(
                "A resource key is in use because no Entra token could be obtained. "
                "The demos work, but this run is not exercising the keyless path."
            )
            st.caption(client.auth_fallback)
        st.caption(
            "Tip: rehearse in fallback, then `az login` for the live run."
            if cfg.keyless_enabled
            else "Tip: rehearse in fallback, then set the keys for the live run."
        )


def main():
    cfg = get_config()
    client = get_client()
    sidebar(cfg, client)

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
