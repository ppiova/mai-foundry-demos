# MAI Examples

A compact Streamlit app that showcases the Microsoft MAI multimodal stack through short,
focused demos designed for a 30–45 minute presentation.

Each demo proves one clear claim about the MAI stack and can run in one of two modes:

- **🟢 LIVE** — uses real MAI APIs when credentials are present in `.env`
- **🟡 FALLBACK** — uses deterministic offline stand-ins so you can rehearse without
  keys and so a live hiccup on stage degrades gracefully

The API surface used here was verified against Microsoft Learn on 2026-08-13. See
[docs/API_VERIFIED.md](docs/API_VERIFIED.md) for the details.

## What this repo demonstrates

The app is organized around four main story beats and a finale:

| Demo | What it shows | Typical setup |
|---|---|---|
| 🧠 Thinking · Decision Agent | Tool-using reasoning over a cloud estate and migration constraints | Foundry resource |
| 🎨 Image · Surgical Edit | Controlled image editing with strong preservation of subject and style | Foundry image resource |
| 🎙️ Transcribe · Entity biasing | Domain-aware transcription with phrase biasing and verbatim mode | Speech resource |
| 🗣️ Voice · Personalities | Expressive TTS with multiple styles and languages | Speech resource |
| 🚀 Finale · Multimodal | End-to-end flow: speech → reasoning → image → speech | Combination of the above |

Backup demos are also included for extra flexibility: Voice personalities and faster image generation.

## Quick start

```bash
# 1. From the project root, create a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # PowerShell (Windows)

# 2. Install
pip install -r requirements.txt

# 3. (Optional) Build the base product image for the edit demo
python assets/build_assets.py

# 4. (Optional) Add credentials to go LIVE
copy .env.example .env               # then edit .env

# 5. Run
streamlit run app.py
```

With no `.env`, everything runs in **FALLBACK** mode — great for rehearsal.

## Going LIVE

Fill any subset of `.env` (see [`.env.example`](.env.example)). Each demo checks
its own credentials, so you can, e.g., run Thinking + Image live while Transcribe
stays in fallback.

| Demo | Needs | Env |
|---|---|---|
| Thinking-1 | Foundry resource | `MAI_FOUNDRY_ENDPOINT`, `MAI_FOUNDRY_API_KEY`, `MAI_THINKING_DEPLOYMENT` |
| Image-2.5 / Flash | Foundry resource (image-capable region) | `MAI_IMAGE_ENDPOINT`, `MAI_IMAGE_API_KEY`, deployment names |
| Transcribe-1.5 | Speech resource | `MAI_SPEECH_ENDPOINT`, `MAI_SPEECH_KEY` |
| Voice-2 (TTS) | Speech resource | `MAI_SPEECH_KEY`, `MAI_SPEECH_REGION` |

Deploy the models in the Foundry portal / Azure CLI first; the `model` field in
each call is the **deployment name** you assign. `.env` is gitignored — never commit
real keys.

Prefer infrastructure as code? [`infra/main.bicep`](infra/main.bicep) deploys the
whole Foundry resource — `MAI-Thinking-1`, `MAI-Image-2.5`, and `MAI-Image-2.5-Flash` —
in one `az deployment group create`. Verified end-to-end against a live Azure
subscription. See [`infra/README.md`](infra/README.md).

### How the models are called

Every model is a deployment on a **Microsoft Foundry** resource (kind `AIServices`),
reached over plain HTTPS:

- **Thinking-1** → OpenAI-compatible `POST {endpoint}/openai/v1/chat/completions`
  (`api-key` header, SSE streaming, standard `tools` / `tool_choice` function calling).
- **Image-2.5 / Flash** → `POST {endpoint}/mai/v1/images/edits` and `/generations`
  (edits are multipart; responses are base64 PNG).
- **Transcribe-1.5** → the Speech **LLM Speech API**
  `POST {speech-endpoint}/speechtotext/transcriptions:transcribe`, with a `phraseList`
  for entity biasing.
- **Voice-2** → the Speech **REST TTS** `POST {region}.tts.speech.microsoft.com/cognitiveservices/v1`
  with SSML `mstts:express-as` styles.

Chat, image, and speech can share one resource or live on separate ones — which is why
`MAI_FOUNDRY_*`, `MAI_IMAGE_*`, and `MAI_SPEECH_*` are configured independently. This
matters in practice: **MAI image models are region-limited** (e.g. not available in
East US 2), so image may need its own resource in a supported region.

All six demos plus the finale were verified end-to-end against a real Foundry
deployment. Full API details and sources: [`docs/API_VERIFIED.md`](docs/API_VERIFIED.md).

## Notes on the MAI lineup (worth knowing)

A few things that came up while verifying against Microsoft's public docs (all
captured in [`docs/API_VERIFIED.md`](docs/API_VERIFIED.md)):

- **Transcribe naming.** The public docs list only `mai-transcribe-1.5` and
  `mai-transcribe-1` (the latter deprecated 2026-08-20). Some early materials
  referenced "MAI-Transcribe-2"; this project standardizes on **1.5**.
- **Preview status.** Image / Transcribe / Voice are **public preview**;
  MAI-Thinking-1 is described as **private preview / "public access coming soon."**
- **Image-2e is deprecated.** It can no longer be deployed; **`MAI-Image-2.5-Flash`**
  is its fast / high-volume successor (used here for generation).
- **Voice styles are voice-dependent.** `mstts:express-as` styles vary by voice — e.g.
  `empathy` exists on `es-ES-Marta` and the multilingual voices, not on the en-US
  voices (which offer `excited`, `hopeful`, `softvoice`, …). The app validates the
  requested style against the voice and falls back to the closest supported one.

## Project layout

```
app.py                     Streamlit entry (4 main tabs + 2 backup tabs)
mai/                       Shared client library
  config.py                Env config, endpoints, voice/style registry
  client.py                MAIClient — pluggable LIVE + FALLBACK for all 4 families
  ssml.py                  SSML builder + style validation
  fallback.py              Deterministic offline stand-ins
demos/                     One module per demo (each exposes render(client))
assets/
  data/                    cloud_estate.json, region_capacity.json (Thinking demo)
  build_assets.py          Generates the base product image
docs/
  API_VERIFIED.md          Verified API surface (with sources)
  PROMPTS.md               Every demo prompt, ready to copy/paste
tests/                     Offline smoke tests (pytest, no credentials)
infra/                     Bicep template to deploy the Foundry resource + model deployments
.github/workflows/ci.yml   Lint (ruff) + offline tests on every push / PR
```

## Tests

The suite runs fully offline in FALLBACK mode — no credentials, no network:

```bash
pip install ruff pytest
ruff check .
pytest
```

CI (`.github/workflows/ci.yml`) runs the same lint + tests on every push and PR.

## Notes

- HTTP is plain `requests`, matching the Microsoft REST docs one-to-one (no SDK
  coupling). Swap in the OpenAI SDK or Azure Speech SDK if you prefer.
- Audible offline voice fallback uses `pyttsx3` (OS TTS) if installed; otherwise
  the demo shows the valid SSML and no audio.
- Fallback outputs are always labelled as mock — never presented as real model output.
