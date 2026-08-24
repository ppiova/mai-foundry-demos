"""Demo 2 — MAI-Image-2.5 "Surgical Marketing Edit".

One instruction, many controlled changes, brand identity preserved. Shows the
"control with preservation" message: rename the label, remove an object, swap the
background — while keeping product, logo, person, angle and lighting.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from mai import MAIClient

BASE_IMAGE = Path(__file__).resolve().parent.parent / "assets" / "images" / "contoso_hydrate.png"

DEFAULT_PROMPT = (
    "Preserve the product, logo, person, camera angle, pose, lighting, and overall "
    "composition exactly. Replace the text 'Summer Edition' with 'Miami Edition' "
    "using typography that matches the existing brand style. Remove the coffee cup "
    "from the table without altering the table, surrounding objects, or scene "
    "balance. Replace the background with a realistic Miami beach at sunset, "
    "keeping depth, color harmony, and a polished commercial-advertising look. "
    "Do not add new objects or change the brand identity."
)

HERO_PROMPT = (
    "Reframe this image as a wide presentation hero shot for a premium marketing "
    "campaign. Preserve the product and person, keep the same camera angle and "
    "lighting, and create clean negative space on the right for a headline and CTA. "
    "Use a polished, high-end commercial style with balanced composition, subtle "
    "depth, and no visual clutter."
)

# Quick, crowd-pleasing prompts for the live free-generation demo (label, prompt).
FUN_PROMPTS = [
    (
        "🐕 Corgi skater",
        "A corgi in tiny sunglasses skateboarding through Times Square at golden hour, photorealistic.",
    ),
    (
        "🤖 Robot barista",
        "A tiny robot barista making latte art, macro shot, shallow depth of field.",
    ),
    (
        "🐱 Space cat",
        "A cat in a spacesuit floating inside a space station, dramatic cinematic lighting.",
    ),
    (
        "☕ Iso coffee shop",
        "Isometric 3D cutaway of a cozy coffee shop, warm lighting, cute miniature style.",
    ),
    ("🖼️ BA watercolor", "A vibrant vintage watercolor travel poster of Buenos Aires at dusk."),
    (
        "🌃 Cyberpunk street",
        "A cyberpunk city street in the rain, neon reflections, blade-runner mood.",
    ),
    (
        "🔤 Neon 'MAI LIVE'",
        'A glowing neon sign that reads "MAI LIVE" on a brick wall at night, bokeh.',
    ),
    (
        "☕ Latte 'FOUNDRY'",
        'A latte with the word "FOUNDRY" drawn in the foam, top-down café shot.',
    ),
    ("🪧 Chalk 'AI COE'", 'A chalkboard cafe sign with "AI COE" in elegant hand lettering.'),
    (
        "🥤 Product mug",
        "Studio product shot of a sleek electric smart mug on marble, soft rim light, premium ad style.",
    ),
    (
        "📊 Holo dashboard",
        "A floating holographic dashboard of glowing data charts in a dark control room, cinematic.",
    ),
]


def ensure_base_image() -> Path:
    if not BASE_IMAGE.exists():
        from assets.build_assets import main as build

        build()
    return BASE_IMAGE


def render(client: MAIClient) -> None:
    st.subheader("🎨 MAI-Image-2.5 — Surgical Marketing Edit")
    st.caption(
        "Object removal · text replacement · background swap — composition & brand preserved."
    )

    mode = "🟢 LIVE" if client.cfg.image_ready else "🟡 FALLBACK (mock edit)"
    st.info(
        f"Mode: **{mode}**  ·  endpoint `/mai/v1/images/edits`  ·  model `{client.cfg.image_edit_deployment}`"
    )

    if not client.cfg.image_ready:
        with st.expander("⚠️ Image API not configured — showing mock results"):
            st.write("Add these to `.env` to run LIVE (see `.env.example`):")
            st.code(
                "MAI_IMAGE_ENDPOINT=https://<your-resource>.services.ai.azure.com\n"
                "MAI_IMAGE_API_KEY=<your-key>\n"
                "MAI_IMAGE_EDIT_DEPLOYMENT=MAI-Image-2.5",
                language="bash",
            )

    ensure_base_image()
    uploaded = st.file_uploader(
        "Optional: use your own product photo (PNG/JPEG)",
        type=["png", "jpg", "jpeg"],
        key="edit_upload",
    )
    if uploaded is not None:
        src_bytes = uploaded.read()
        mime = uploaded.type or "image/png"
        fname = uploaded.name
    else:
        src_bytes = BASE_IMAGE.read_bytes()
        mime, fname = "image/png", "contoso_hydrate.png"

    st.caption(
        "Write a clear instruction for MAI: tell it what to preserve, what to change, and the style you want."
    )
    prompt = st.text_area(
        "Edit instruction",
        value=DEFAULT_PROMPT,
        height=120,
        key="edit_prompt",
        help="Example: preserve the product and person, replace the text, remove an object, and change the background while keeping the brand look intact.",
    )

    col_run, col_hero = st.columns([1, 1])
    run = col_run.button("▶ Run edit", type="primary", key="edit_run")
    hero = col_hero.button("▶ Second edit: hero composition", key="edit_hero")

    if run or hero:
        active_prompt = HERO_PROMPT if hero else prompt
        with st.spinner("Editing…"):
            result = client.edit_image(src_bytes, active_prompt, filename=fname, mime=mime)

        # Status badge with mode indicator
        status = f"**{result.badge}**  ·  {result.elapsed:.1f}s"
        if result.error:
            st.error(f"❌ **API Error** — using fallback mock\n\n```\n{result.error}\n```")
            st.info("**Tip:** Check MAI_IMAGE_ENDPOINT and MAI_IMAGE_API_KEY in `.env`")
        else:
            st.success(f"✅ {status}")

        st.markdown(status)
        left, right = st.columns(2)
        left.markdown("**Original**")
        left.image(src_bytes, width="stretch")
        right.markdown("**Edited**")
        right.image(result.data, width="stretch")
        st.download_button(
            "Download edited PNG",
            result.data,
            file_name="edited.png",
            mime="image/png",
            key="edit_dl",
        )

    # ── Free generation (text-to-image, any prompt) ──────────────────────────
    st.divider()
    st.markdown("### ✨ Free generation — type any prompt")
    st.caption("Generate any image from scratch (text-to-image), not just product edits.")

    st.session_state.setdefault("gen_prompt", FUN_PROMPTS[0][1])
    with st.expander("🎲 Fun example prompts (click to load)"):
        st.caption("Tip: for the text-in-image ones, swap the quoted word for the event or a name.")
        cols = st.columns(2)
        for i, (label, ptext) in enumerate(FUN_PROMPTS):
            cols[i % 2].button(
                label,
                key=f"gen_ex_{i}",
                width="stretch",
                on_click=lambda p=ptext: st.session_state.update(gen_prompt=p),
            )

    gen_prompt = st.text_area(
        "Prompt", key="gen_prompt", height=90, placeholder="Describe anything you want to generate…"
    )
    gc1, gc2, gc3 = st.columns([1.6, 1, 1])
    gen_model = gc1.selectbox(
        "Model",
        [
            f"{client.cfg.image_edit_deployment} (quality)",
            f"{client.cfg.image_gen_deployment} (fast)",
        ],
        key="gen_model",
    )
    gen_deploy = (
        client.cfg.image_edit_deployment
        if "quality" in gen_model
        else client.cfg.image_gen_deployment
    )
    gen_size = gc2.select_slider("Size", options=[768, 896, 1024], value=1024, key="gen_size")
    gen_go = gc3.button("✨ Generate", type="primary", key="gen_run", width="stretch")
    if gen_go:
        if not gen_prompt.strip():
            st.warning("Enter a prompt first.")
        else:
            with st.spinner(f"Generating with {gen_deploy}…"):
                gres = client.generate_image(
                    gen_prompt.strip(), width=gen_size, height=gen_size, deployment=gen_deploy
                )
            st.markdown(f"**{gres.badge}** · {gen_deploy} · {gres.elapsed:.1f}s")
            if gres.error:
                st.warning(f"Live call failed → mock shown. Detail: {gres.error}")
            st.image(gres.data, width="stretch", caption=gen_prompt.strip())
            st.download_button(
                "Download PNG", gres.data, file_name="generated.png", mime="image/png", key="gen_dl"
            )
