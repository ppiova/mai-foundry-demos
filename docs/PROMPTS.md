# Prompts & scripts — copy/paste reference

## 1 · MAI-Thinking-1 — Enterprise Decision Agent

User objective (already wired into the demo):

```
We need to reduce cloud cost by 20% without moving Tier-1 applications and
without exceeding 70% capacity in any region. Build a migration plan and explain
the tradeoffs.
```

Tools available to the model: `get_region_capacity(region)`,
`calculate_migration_cost(app_names, target_region)`.

## 2 · MAI-Image-2.5 — Surgical Marketing Edit

First edit:

```
Preserve the product, logo, person, camera angle, pose, lighting, and overall
composition exactly. Replace the text "Summer Edition" with "Miami Edition"
using typography that matches the existing brand style. Remove the coffee cup from
the table without altering the table, surrounding objects, or scene balance.
Replace the background with a realistic Miami beach at sunset, keeping depth,
color harmony, and a polished commercial-advertising look. Do not add new
objects or change the brand identity.
```

Second edit (reframe):

```
Reframe this image as a 16:9 presentation hero shot for a premium marketing
campaign. Preserve the product and person, keep the same camera angle and
lighting, and create clean negative space on the right for a headline and CTA.
Use a polished, high-end commercial style with balanced composition, subtle
depth, and no visual clutter.
```

## 3 · MAI-Transcribe-1.5 — Entity biasing

Spoken script (say it, or click "Generate sample audio"):

```
Yesterday the Fabrikam XQ-17 team deployed KEDA and Dapr on AKS. The incident was
escalated to Rehaan and Jessie, and we tracked it in the MAI-Thinking-1 workspace
before rolling back.
```

phraseList:

```
Fabrikam XQ-17, KEDA, Dapr, AKS, Rehaan, Jessie, MAI-Thinking-1
```

Toggle `verbatim` to preserve fillers/disfluencies.

## 4 · MAI-Voice-2 — Three personalities

Text (English):

```
I found the problem with your order. The replacement has already been shipped and
will arrive tomorrow.
```

Text (Español — multilingual close):

```
Encontré el problema con tu pedido. El reemplazo ya fue enviado y va a llegar mañana.
```

Buttons: **Neutral** (no style) · **Empathy** (`empathy`, use es-ES-Marta for the
real style) · **Excited** (`excited`). `styledegree` slider for intensity.

## 5 · MAI-Image-2.5-Flash — Speed at scale

Prompt template (color/background vary in a loop):

```
Studio product photo of a modern travel mug, {color}, clean {background}
background, ecommerce photography.
```

## Finale · Multimodal Campaign Agent

Spoken brief:

```
Create a launch campaign for a new sustainable smart backpack targeted at business
travelers.
```

Pipeline: Transcribe-1.5 (speech→text) → Thinking-1 (name, tagline, brief,
hero prompt, VO script) → Image-2.5 (hero) → Voice-2 (15s voice-over).

## Free generation — fun example prompts

The Image tab's "Free generation" section ships these as one-click chips (2.5 for
quality, Flash for speed):

- A corgi in tiny sunglasses skateboarding through Times Square at golden hour, photorealistic.
- A tiny robot barista making latte art, macro shot, shallow depth of field.
- A cat in a spacesuit floating inside a space station, dramatic cinematic lighting.
- Isometric 3D cutaway of a cozy coffee shop, warm lighting, cute miniature style.
- A cyberpunk city street in the rain, neon reflections, blade-runner mood.
- A glowing neon sign that reads "MAI LIVE" on a brick wall at night, bokeh.

Tip: for the text-in-image prompts (`"MAI LIVE"`, `"FOUNDRY"`, …), swap in the event
or a person's name — MAI-Image-2.5 renders text well, which lands as a live "wow".
