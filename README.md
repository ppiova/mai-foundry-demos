---
name: MAI Foundry demos
description: Explore multimodal MAI capabilities, validate model proposals, and distinguish offline rehearsal from live evidence.
languages:
- python
- bicep
products:
- azure
- ai-services
page_type: sample
urlFragment: mai-foundry-demos
---

# MAI Foundry Demos

**Explore MAI capabilities. Validate the output. Follow the evidence.**

[![CI (main)](https://github.com/ppiova/mai-foundry-demos/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ppiova/mai-foundry-demos/actions/workflows/ci.yml)
[![CodeQL (main)](https://github.com/ppiova/mai-foundry-demos/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/ppiova/mai-foundry-demos/actions/workflows/codeql.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE.md)

**Current release: [v2.0.0](CHANGELOG.md#200---2026-09-20)** ·
**[Upgrading from v1.1.1](docs/UPGRADING.md)**

Built by **[Pablo Piovano](https://www.linkedin.com/in/ppiova/)** ·
**[Microsoft MVP](https://mvp.microsoft.com/en-US/mvp/profile/33e06bb6-ccb0-ec11-983f-000d3a1017e3) ·
[Docker Captain](https://www.docker.com/contributors/pablo-piovano/)**

A compact Streamlit app and teaching kit for exploring the Microsoft MAI multimodal
stack. Use it for a 30–45 minute developer presentation, or follow the
**[45-minute Thinking workshop](docs/THINKING_WORKSHOP.md)** without an Azure account.

**[Run offline](#run-it-offline-first) → [Try the workshop](docs/THINKING_WORKSHOP.md) →
[Understand the design](docs/DESIGN_DECISIONS.md) → [Verify a LIVE run](#verify).**

**[Results](#a-result-you-can-reproduce) · [Demos](#features) ·
[Quick start](#run-it-offline-first) · [Azure](#go-live) · [Costs](#costs) ·
[Deep dives](#go-deeper) · [Project policies](#project-policies)**

> Independent community project. Not an official Microsoft product or a
> Microsoft-supported sample. The offline path uses fictional data and makes
> no Azure inference calls. LIVE execution is optional and can incur charges.

**For:** Python developers, cloud architects, and technical presenters who know basic
Python and JSON. No prior agent framework experience is required.

**Learn to:** trace a tool-calling loop, separate model proposals from deterministic
validation, distinguish offline rehearsal from live evidence, and reproduce a demo
with explicit authentication, cost, and failure boundaries. This is not an automated
migration tool or a production reference architecture.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/ppiova/mai-foundry-demos)

**En español:** empieza por la [ruta offline](#run-it-offline-first) y sigue el
[taller de Thinking](docs/THINKING_WORKSHOP.md). No necesitas Azure: validarás un
plan sobre datos ficticios, sin ejecutar migraciones. **FALLBACK no demuestra
razonamiento del modelo.** Puedes enviar preguntas o feedback en español.

Each demo illustrates one capability and can run in one of two modes:

- **🟢 LIVE**, using the real MAI APIs when the services are configured
- **🟡 FALLBACK**, using deterministic offline stand-ins so you can rehearse without
  any Azure resources, and so a live hiccup on stage degrades gracefully

Fallback output is always labelled as such. It is never presented as real model output.
It teaches the application contract, not model quality or live authentication.

[![MAI Examples demo interface](assets/images/demo-ui-screenshot.png)](assets/images/demo-ui-screenshot.png)

Expected starting point: a service-status sidebar and a **Thinking · Decision Agent**
tab. The [existing UI capture](assets/images/demo-ui-screenshot.png) is an orientation
aid, not evidence that your own run is live.

The field report that came out of this work, including what broke and what it took to
make the demos repeatable:
**[Four MAI Capabilities, One Live App: Field Notes from Microsoft Foundry](https://www.linkedin.com/pulse/four-mai-capabilities-one-live-app-field-notes-from-foundry-piovano-fomse)**,
describing tag [`v1.1.1`](https://github.com/ppiova/mai-foundry-demos/releases/tag/v1.1.1).
That published release predates the keyless changes introduced in v2.0.0.
Use the checked-out revision and [verification record](docs/API_VERIFIED.md) to
identify what applies; the older release is not evidence of current keyless behavior.

## A result you can reproduce

Start with the Thinking demo in **FALLBACK**, using the bundled fictional estate:

| Observation | Expected result | What it demonstrates |
|---|---|---|
| Monthly cost | $177,000 → about $140,704 | Arithmetic over sample data, not an Azure bill |
| Savings | 20.5% | The deterministic proposal meets the encoded 20% floor |
| Actions | 6 moves, 3 decommissions | A greedy local planner, not model-selected actions |
| Regions above the 70% ceiling | 0 | Cumulative validation of the complete proposal |

**The model proposes; code validates.** The
[workshop](docs/THINKING_WORKSHOP.md) also combines two individually acceptable
moves into a rejected plan. That failure is part of the lesson.
These reproducible results do not establish model quality, an optimal migration,
or production readiness.

## Features

These are four selected MAI capabilities, not an exhaustive catalog of the MAI family.
The app is organized around four story beats and a finale:

| Demo | What it shows | Needs |
|---|---|---|
| 🧠 Thinking · Decision Agent | Tool-using reasoning over a cloud estate and migration constraints | Foundry resource |
| 🎨 Image · Surgical Edit | Controlled image editing with preservation-oriented prompts | Foundry image resource |
| 🎙️ Transcribe · Entity biasing | Compare phrase biasing; 1.5 is already verbatim | Speech resource |
| 🗣️ Voice · Personalities | Expressive TTS with multiple styles and languages | Speech resource |
| 🚀 Finale · Multimodal | End-to-end flow: speech, reasoning, image, speech | Combination of the above |

Two backup demos are included for extra flexibility: voice personalities and faster
image generation.

Beyond the demos themselves:

- **Entra preferred by default.** Microsoft Entra ID and Azure RBAC need no secret.
  A configured resource key can take over if token acquisition fails; leave keys
  empty when verifying keyless behavior.
- **Per-service configuration.** Each demo checks its own service, so you can run
  Thinking and Image live while Transcribe stays in fallback.
- **A documented API surface.** [`docs/API_VERIFIED.md`](docs/API_VERIFIED.md) records
  every call, its source in Microsoft Learn, and whether it was verified live.
- **Infrastructure as code.** [`infra/main.bicep`](infra/main.bicep) deploys the Foundry
  resource, the model deployments, and the role assignments in one command.
- **Offline test suite.** Domain, API-contract, authentication, and UI regression
  checks, with no credentials or network.

## Getting Started

### Prerequisites

- Python 3.11 or later
- An Azure subscription, for the LIVE path only. Everything runs in FALLBACK without one.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), only for the
  optional LIVE path (keyless sign-in and infrastructure deployment)

### Run it offline first

No Azure resources or sign-in are needed. Install dependencies before disconnecting:
**offline-first refers to running the demo, not downloading Python packages**.
Open Codespaces above, or get the code locally with Git (either shell):

```text
git clone https://github.com/ppiova/mai-foundry-demos.git
cd mai-foundry-demos
```

Run from the repository root in either shell. The constrained install pins direct
dependencies for repeatability; it is not a lock of every transitive dependency.

**Bash (Linux/macOS, or a Codespaces terminal):**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints.txt
export MAI_EXECUTION_MODE=demo
export MAI_AUTH_MODE=key
for name in MAI_FOUNDRY_ENDPOINT MAI_IMAGE_ENDPOINT MAI_SPEECH_ENDPOINT \
            MAI_FOUNDRY_API_KEY MAI_IMAGE_API_KEY MAI_SPEECH_KEY; do
  export "$name= "
done
python -m streamlit run app.py
```

**PowerShell (Windows):**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -c constraints.txt
$env:MAI_EXECUTION_MODE = "demo"
$env:MAI_AUTH_MODE = "key"
foreach ($name in @(
    "MAI_FOUNDRY_ENDPOINT", "MAI_IMAGE_ENDPOINT", "MAI_SPEECH_ENDPOINT",
    "MAI_FOUNDRY_API_KEY", "MAI_IMAGE_API_KEY", "MAI_SPEECH_KEY"
)) {
    Set-Item -Path "Env:$name" -Value " "
}
python -m streamlit run app.py
```

Use another installed Python 3.11+ version if needed. If activation is blocked by
your organization's PowerShell policy, do not change that policy: run
`.\.venv\Scripts\python.exe` instead of `python` for installation and startup.

The single-space overrides are intentional: configuration strips them to empty,
while `python-dotenv` will not reload an existing `.env` value over them. This also
works in PowerShell versions where assigning an empty string removes a variable.
`demo` alone does **not** force offline mode: it still calls configured services.
These overrides affect only this terminal and its child processes.

Open `http://localhost:8501` (the forwarded **8501 / Streamlit** port in Codespaces).
All services should show **FALLBACK**. In **Thinking · Decision Agent**, click
**▶ Run decision agent**. Expect a labelled offline plan, **Deterministic
validation**, **20.5%** verified savings, **6** apps moved, **3** decommissioned,
and **0** regions over the ceiling for the bundled fictional estate.

Use the [workshop](docs/THINKING_WORKSHOP.md) for exercises and facilitator notes,
and [design decisions](docs/DESIGN_DECISIONS.md) to understand the tradeoffs.
Stop Streamlit with **Ctrl+C**. No cloud cleanup is needed for this path.

### Deploy the Azure resources (optional)

Only after the offline run, review [`infra/README.md`](infra/README.md) for
deployment steps, permissions, cost controls, quota, region constraints, and
teardown. Nothing in the workshop requires deploying infrastructure.

The template can deploy `MAI-Thinking-1`, `MAI-Image-2.5`, and
`MAI-Image-2.5-Flash`. Confirm availability and quota in your own subscription
first; the recorded Thinking quota limitation is not solved by changing regions.

### Go LIVE

Stop the offline app and use a **new terminal** so the offline overrides above
cannot hide your LIVE settings. Copy the template only if `.env` does not already
exist; never overwrite a working configuration or commit secrets.

**Bash:**

```bash
source .venv/bin/activate
test -f .env || cp .env.example .env
# Edit .env using the table below before continuing.
export MAI_AUTH_MODE=entra
export MAI_EXECUTION_MODE=strict
az login
python -m streamlit run app.py
```

**PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env using the table below before continuing.
$env:MAI_AUTH_MODE = "entra"
$env:MAI_EXECUTION_MODE = "strict"
az login
python -m streamlit run app.py
```

Keyless needs endpoints and resource/deployment configuration, never a secret:

| Demo | Env |
|---|---|
| Thinking-1 | `MAI_FOUNDRY_ENDPOINT`, `MAI_THINKING_DEPLOYMENT` |
| Image-2.5 / Flash | `MAI_IMAGE_ENDPOINT`, deployment names |
| Transcribe-1.5 | `MAI_SPEECH_ENDPOINT` |
| Voice-2 (TTS) | `MAI_SPEECH_ENDPOINT`, `MAI_SPEECH_RESOURCE_ID`, `MAI_SPEECH_REGION` |

Chat, image, and speech are configured independently, which is what lets Image point at
a different resource when regional availability requires it. All of them can also point
at the same account.

To use resource keys instead, set `MAI_AUTH_MODE=key` and fill in `MAI_*_API_KEY` and
`MAI_SPEECH_KEY`. That path needs an account deployed with `disableLocalAuth = false`.
Keys can also be used as a safety net in `entra` mode if token acquisition fails.
For a keyless-only check, leave all keys blank in `.env` **and** the process
environment. `strict` does not disable this authentication safety net.

**Read the result, not just the configuration indicator.** A service configured for
LIVE has not yet proved it can answer. Thinking must finish with `source="live"`
and a passing deterministic validation. The
[verification record](docs/API_VERIFIED.md) distinguishes documented contracts,
offline tests, and dated live checks; the 2026-09-11 authentication checks did
**not** establish Thinking keyless live success because quota blocked that check.

### Verify

In the new LIVE terminal, after reviewing the services you intend to call:

```bash
MAI_EXECUTION_MODE=strict python scripts/live_smoke.py
```

```powershell
$env:MAI_EXECUTION_MODE = "strict"
python scripts\live_smoke.py
```

By default the script requires all four services. For an intentionally limited
Thinking-only setup, append `--allow-partial`; it still calls **every configured
service**, so keep Image/Speech unconfigured if you do not intend to use them.
If Transcribe is configured but Voice cannot produce LIVE audio for its input,
the check **fails**, including in partial mode. Partial mode never turns an
unexercised configured service into a pass.

Calls may incur usage charges. The smoke checks cover chat/tool-call transport,
image **generation**, basic voice synthesis, and transcription of that generated
audio. They do **not** verify image editing/preservation, voice styles, phrase-bias
quality, or the complete decision-agent plan. See the
[verification matrix](docs/API_VERIFIED.md) for the distinct evidence boundaries.

Use strict mode for preflight, authentication checks, measurements, and any claim
about model behavior. `MAI_EXECUTION_MODE=demo` permits labelled fallback for
rehearsal or presentation continuity. The agent also replaces a rejected or
unstructured model plan with its offline plan, even in strict mode: check the
**final source, warnings, and validation**, not just whether an exception occurred.

## Guidance

### How the models are called

Two service surfaces, both over HTTPS with `requests`, keeping the REST payloads
visible for teaching rather than hiding them behind an inference SDK:

- **Thinking-1** to `POST {endpoint}/mai/v1/chat/completions`, with SSE streaming,
  `tools` function calling, `max_completion_tokens`, and `reasoning_display` for
  encrypted reasoning state across tool rounds.
- **Image-2.5 / Flash** to `POST {endpoint}/mai/v1/images/edits` and `/generations`.
  Edits are multipart; responses are base64 PNG.
- **Transcribe-1.5** to the Speech LLM Speech API
  `POST {speech-endpoint}/speechtotext/transcriptions:transcribe`, with a `phraseList`
  for entity biasing.
- **Voice-2** to the Speech REST TTS `cognitiveservices/v1` path with SSML
  `mstts:express-as` styles.

`azure-identity` is still used for Entra tokens: REST inference does not mean
"no SDK anywhere." An SDK could reduce transport/streaming boilerplate, but would
need to preserve these endpoint-specific fields and error semantics. See
[design decisions](docs/DESIGN_DECISIONS.md) for why the sample keeps them explicit.

### Authentication

Entra is the default preference. The two service families use different token audiences, which is
the detail that most often costs an afternoon:

| Service | Scope | Role |
|---|---|---|
| Thinking, Image | `https://ai.azure.com/.default` | Cognitive Services User |
| Transcribe, Voice | `https://cognitiveservices.azure.com/.default` | Cognitive Services Speech User |

Speech additionally requires a custom subdomain on the resource (a prerequisite for
Entra eligibility, verified live not to be the host TTS requests actually reach), and
keyless text to speech requires the resource ID, because that path takes the token as
`aad#<resourceId>#<token>` against the regional TTS host. Full details, including a
live-verified gotcha with `DefaultAzureCredential` picking an unexpected identity, are
in section 0 of [`docs/API_VERIFIED.md`](docs/API_VERIFIED.md).

```mermaid
flowchart LR
    App["Streamlit app"]

    subgraph Auth["DefaultAzureCredential"]
        T1["ai.azure.com/.default"]
        T2["cognitiveservices.azure.com/.default"]
    end

    subgraph Account["Foundry account (custom subdomain)"]
        Think["MAI-Thinking-1"]
        Image["MAI-Image-2.5 / Flash"]
        Trans["MAI-Transcribe-1.5"]
        Voice["MAI-Voice-2"]
    end

    Fallback["Deterministic fallback<br/>labelled, never live"]

    App --> T1
    App --> T2
    T1 -- "Bearer token" --> Think
    T1 -- "Bearer token" --> Image
    T2 -- "Bearer token" --> Trans
    T2 -- "Bearer aad#resourceId#token" --> Voice

    Think -. "any failure, demo mode" .-> Fallback
    Image -. "" .-> Fallback
    Trans -. "" .-> Fallback
    Voice -. "" .-> Fallback
```

Two audiences, one account, and only the text to speech leg wraps the token with
the resource ID. Every dotted edge represents permitted degradation in **demo** mode; strict
transport/API failures raise instead. Service configuration remains independent,
although a composed demo can still depend on another service's output.

If a demo shows FALLBACK when you expected LIVE, see the checklist in
[SUPPORT.md](SUPPORT.md). Role assignments take up to five minutes to propagate.

### Costs

The offline path makes no Azure inference calls. The LIVE path incurs service
usage charges; do not treat a short demo or a successful deployment as a budget
guarantee.

The Bicep model deployments use **`GlobalStandard`**, not Provisioned throughput.
[Microsoft's deployment-type guide](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/deployment-types)
distinguishes consumption-based Standard deployments from **reserved PTU capacity**
in Provisioned deployments. Allocating **TPM quota is a throughput limit, not a
fixed recurring capacity bill**.

Check each service's current meter before a run; not every service bills tokens:

| Capability | Official pricing / meter reference |
|---|---|
| Thinking | [Microsoft Foundry pricing](https://azure.microsoft.com/pricing/details/microsoft-foundry/) — check the selected model's input/output usage meters |
| Image / Flash | [Microsoft Foundry pricing](https://azure.microsoft.com/pricing/details/microsoft-foundry/) — check the selected image model and operation, rather than assuming chat-token pricing |
| Transcribe | [Speech pricing](https://azure.microsoft.com/pricing/details/speech/) — audio-duration billing; verify the applicable LLM Speech offer |
| Voice | [Speech pricing](https://azure.microsoft.com/pricing/details/speech/) — speech-synthesis character billing; verify the selected MAI voice offer |

For a workshop, prefer offline, configure only the service you need, agree a small
number of LIVE attempts, and monitor actual consumption. Thinking can make several
requests per run; the UI agent has **no configured completion-token cap**. Its
round/read-timeout limits are not spending limits. Codespaces, if used, has its own
billing separate from Azure inference. See the
[LIVE workshop checklist](docs/THINKING_WORKSHOP.md#optional-live-branch) and
[infrastructure cleanup guidance](infra/README.md#tear-down). This sample quotes no
prices and does not estimate your bill.

### Notes on the MAI lineup

All of these are recorded, with sources, in [`docs/API_VERIFIED.md`](docs/API_VERIFIED.md):

- **Preview status.** Microsoft Learn currently labels MAI-Thinking-1 and the selected
  Image, Transcribe, and Voice capabilities as preview. Preview capabilities can change.
- **Transcribe generations.** `MAI-Transcribe-2` is now documented alongside
  `mai-transcribe-1.5`, and `MAI-Transcribe-1` was deprecated on 2026-08-20. This sample
  targets `mai-transcribe-1.5`, the version its live runs were measured against.
  Verified live: `mai-transcribe-1.5` only ever produces verbatim output, and rejects
  `clean` outright (Transcribe-2 supports both). See `docs/API_VERIFIED.md` section 3.
- **Deployment names are configurable.** The `model` field in each call is the deployment
  name you assign, not a fixed model ID.
- **Voice styles are voice-dependent.** `empathy` exists on `es-ES-Marta` and the
  multilingual voices, not on the en-US voices, which offer `excited`, `hopeful`,
  `softvoice` and others. The app validates the requested style against the voice and
  falls back to the closest supported one.

### Development

In the virtual environment created above:

```bash
python -m pip install ruff pytest
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

The suite is fully offline and hermetic: no credentials, no network, and no dependence
on who is signed in to Azure. CI runs the same checks on Python 3.11 and 3.13, plus
CodeQL and PSRule for Azure against the Bicep, on every push and pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

```
app.py                     Streamlit entry (4 main tabs + 2 backup tabs)
mai/                       Shared client library
  auth.py                  Microsoft Entra ID tokens, per audience
  config.py                Env config, endpoints, voice/style registry
  client.py                MAIClient, pluggable LIVE + FALLBACK for all 4 families
  ssml.py                  SSML builder + style validation
  fallback.py              Deterministic offline stand-ins
agents/                    Demo domain logic, independent of the UI
  estate.py                The cloud estate and the two tools the model may call
  plan.py                  Plan types, the deterministic validator, rendering
  decision.py              The live tool-calling loop and the greedy fallback planner
demos/                     One module per demo (each exposes render(client))
assets/data/               cloud_estate.json, region_capacity.json (Thinking demo)
docs/
  UPGRADING.md             v1.1.1 to v2.0.0 configuration changes and known limits
  API_VERIFIED.md          Verified API surface, with sources
  PROMPTS.md               Every demo prompt, ready to copy and paste
  THINKING_WORKSHOP.md     45-minute offline-first tutorial and facilitator notes
  DESIGN_DECISIONS.md      REST, validation, fallback, and sample-only boundaries
  IMAGE_PRESERVATION.md    What the image edit actually preserved, measured
scripts/
  live_smoke.py            Strict preflight against all four services
  measure_preservation.py  Reproduces the numbers in IMAGE_PRESERVATION.md
tests/                     Offline tests (pytest, no credentials)
infra/                     Bicep: Foundry resource, model deployments, role assignments
.devcontainer/             One-click Codespace, offline run with no Azure account
ps-rule.yaml               PSRule config, including the documented rule exclusions
constraints.txt            Pinned versions for a run that matters
```

## Go deeper

| Document | Read it when you want to |
|---|---|
| [Upgrade guide](docs/UPGRADING.md) | Move from v1.1.1 to v2.0.0, review changed defaults, and verify without confusing fallback with live evidence |
| [Thinking workshop](docs/THINKING_WORKSHOP.md) | Teach or complete the 45-minute lab, including expected results and an unsafe-plan exercise |
| [Design decisions](docs/DESIGN_DECISIONS.md) | Trace REST, tools, validation and fallback, and understand what would need to change for production |
| [API sources and verification](docs/API_VERIFIED.md) | Follow service-specific claims to official documentation and distinguish dated live evidence from untested paths |
| [Image preservation observation](docs/IMAGE_PRESERVATION.md) | Reproduce the measurements for one recorded image pair without treating it as a benchmark |
| [Prompts and scripts](docs/PROMPTS.md) | Rehearse the other demos with the exact prompts and known limitations |

## Microsoft resources

- [Microsoft Foundry documentation](https://learn.microsoft.com/azure/ai-foundry/)
- [MAI-Thinking-1](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/use-foundry-models-mai-thinking)
- [MAI-Image-2.5](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image)
- [MAI-Transcribe-1.5](https://learn.microsoft.com/azure/ai-services/speech-service/mai-transcribe)
- [MAI-Voice-2](https://learn.microsoft.com/azure/ai-services/speech-service/mai-voices)
- [Keyless authentication with Microsoft Entra ID](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/configure-entra-id)
- [`docs/API_VERIFIED.md`](docs/API_VERIFIED.md), the verified API surface for this repo
- [`docs/PROMPTS.md`](docs/PROMPTS.md), every demo prompt

## Important Security Notice

This template, the application code, and the configuration it deploys are built to
showcase Microsoft Azure services and are **not** intended to be used as-is in
production. Treat it as a starting point, and review it against your own requirements.

- It deploys with `publicNetworkAccess: 'Enabled'` for a self-contained demo. Production
  deployments should use private endpoints.
- It applies the service default content filtering. Review those defaults for your use
  case.
- It generates text, images, and speech with preview models. Outputs are not reviewed or
  fact-checked beyond the service defaults, and the sample data is fictional.

With any AI solution you build from this code, you are responsible for assessing the
associated risks and for complying with all applicable laws and safety standards. See
[SECURITY.md](SECURITY.md) for the security posture and for how to report a
vulnerability privately.

## Project policies

| Document | Purpose |
|---|---|
| [Contributing](CONTRIBUTING.md) | Editorial conventions, small contributions and local validation |
| [Code of conduct](CODE_OF_CONDUCT.md) | Community expectations and the maintainer's private reporting route |
| [Security](SECURITY.md) | Vulnerability reporting, credential handling and sample boundaries |
| [Support](SUPPORT.md) | Setup help, learning questions and what this project cannot support |
| [Changelog](CHANGELOG.md) | Notable changes and release history |
| [MIT License](LICENSE.md) | Terms for using and contributing to the code |

## Trademarks

This project may contain trademarks or logos for projects, products, or services.
Authorized use of Microsoft trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause
confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos is
subject to those third parties' policies.

---

**Pablo Piovano · Microsoft MVP · Docker Captain** · [GitHub](https://github.com/ppiova)

Released under the [MIT License](LICENSE.md).
