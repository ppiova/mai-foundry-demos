"""Demo 5 (backup) — MAI-Image-2.5-Flash batch variations.

Generate several simple product variations in a loop and report the observed time.
The UI makes no latency or throughput guarantee.
"""

from __future__ import annotations

import streamlit as st

from mai import MAIClient

PROMPT_TEMPLATE = (
    "Studio product photo of a modern travel mug, {color}, clean {background} "
    "background, ecommerce photography."
)

VARIATIONS = [
    {"color": "matte black", "background": "white"},
    {"color": "sky blue", "background": "light grey"},
    {"color": "forest green", "background": "beige"},
    {"color": "coral red", "background": "white"},
    {"color": "champagne gold", "background": "charcoal"},
    {"color": "lavender", "background": "soft pink"},
]


def render(client: MAIClient) -> None:
    st.subheader("⚡ MAI-Image-2.5-Flash — Batch variations")
    st.caption("Generate several product variations and display observed request timing.")

    st.info(
        f"Mode: **{'🟢 LIVE' if client.cfg.image_ready else '🟡 FALLBACK (mock)'}**  ·  "
        f"deployment `{client.cfg.image_gen_deployment}`  ·  timing is measured for this run only."
    )

    n = st.slider("Number of variations", 2, len(VARIATIONS), 6, key="sp_n")
    size = st.select_slider("Size", options=[768, 896, 1024], value=768, key="sp_size")

    if st.button("▶ Generate batch", type="primary", key="sp_run"):
        combos = VARIATIONS[:n]
        results, total = [], 0.0
        prog = st.progress(0.0, text="Generating…")
        for i, combo in enumerate(combos):
            prompt = PROMPT_TEMPLATE.format(**combo)
            res = client.generate_image(prompt, width=size, height=size)
            results.append((combo, res))
            total += res.elapsed
            prog.progress((i + 1) / len(combos), text=f"{i + 1}/{len(combos)} · {total:.1f}s")
        prog.empty()

        badge = "🟢 LIVE" if all(r.is_live for _, r in results) else "🟡 FALLBACK"
        avg = total / max(1, len(results))
        st.markdown(
            f"**{badge}** · {len(results)} images · **total {total:.1f}s** · avg {avg:.2f}s/image"
        )
        if any(r.error for _, r in results):
            st.warning("Some live calls failed → mock images shown.")

        cols = st.columns(3)
        for i, (combo, res) in enumerate(results):
            with cols[i % 3]:
                st.image(
                    res.data,
                    width="stretch",
                    caption=f"{combo['color']} / {combo['background']} · {res.elapsed:.2f}s",
                )
