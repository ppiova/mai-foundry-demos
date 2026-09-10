# MAI Foundry Demos

A compact Streamlit app that showcases the Microsoft MAI multimodal stack through short,
focused demos designed for a 30 to 45 minute presentation.

Each demo illustrates one capability and can run in one of two modes:

- **🟢 LIVE**, using the real MAI APIs when the services are configured
- **🟡 FALLBACK**, using deterministic offline stand-ins so you can rehearse without
  any Azure resources, and so a live hiccup on stage degrades gracefully

Fallback output is always labelled as such. It is never presented as real model output.

![MAI Examples demo interface](assets/images/demo-ui-screenshot.png)

The field report that came out of this work, including what broke and what it took to
make the demos repeatable:
**[Four MAI Capabilities, One Live App: Field Notes from Microsoft Foundry](https://www.linkedin.com/pulse/four-mai-capabilities-one-live-app-field-notes-from-foundry-piovano-fomse)**,
describing tag [`v1.1.1`](https://github.com/ppiova/mai-foundry-demos/releases/tag/v1.1.1).

## Features

These are four selected MAI capabilities, not an exhaustive catalog of the MAI family.
The app is organized around four story beats and a finale:

| Demo | What it shows | Needs |
|---|---|---|
| 🧠 Thinking · Decision Agent | Tool-using reasoning over a cloud estate and migration constraints | Foundry resource |
| 🎨 Image · Surgical Edit | Controlled image editing with preservation-oriented prompts | Foundry image resource |
| 🎙️ Transcribe · Entity biasing | Domain-aware transcription with phrase biasing and verbatim mode | Speech resource |
| 🗣️ Voice · Personalities | Expressive TTS with multiple styles and languages | Speech resource |
| 🚀 Finale · Multimodal | End-to-end flow: speech, reasoning, image, speech | Combination of the above |

Two backup demos are included for extra flexibility: voice personalities and faster
image generation.

Beyond the demos themselves:

- **Keyless by default.** Microsoft Entra ID and Azure RBAC, with no secret to store.
  Resource keys remain available as an explicit opt-in.
- **Per-service configuration.** Each demo checks its own service, so you can run
  Thinking and Image live while Transcribe stays in fallback.
- **A documented API surface.** [`docs/API_VERIFIED.md`](docs/API_VERIFIED.md) records
  every call, its source in Microsoft Learn, and whether it was verified live.
- **Infrastructure as code.** [`infra/main.bicep`](infra/main.bicep) deploys the Foundry
  resource, the model deployments, and the role assignments in one command.
- **Offline test suite.** 100 tests, no credentials, no network.

## Getting Started

### Prerequisites

- Python 3.11 or later
- An Azure subscription, for the LIVE path only. Everything runs in FALLBACK without one.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), for keyless
  sign-in and for deploying the infrastructure

### Run it offline first

No Azure resources are needed for this, and it is the recommended way to rehearse.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python assets/build_assets.py      # optional: builds the base product image
streamlit run app.py
```

For a run that matters, pin the exact verified versions:

```bash
pip install -r requirements.txt -c constraints.txt
```

### Deploy the Azure resources

```bash
az group create --name rg-mai-examples --location eastus
az ad signed-in-user show --query id -o tsv     # your principalId, for main.bicepparam
az deployment group create \
  --resource-group rg-mai-examples \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam
```

The template deploys `MAI-Thinking-1`, `MAI-Image-2.5`, and `MAI-Image-2.5-Flash`, and
assigns the two roles the app needs. See [`infra/README.md`](infra/README.md) for
quota, region constraints, and teardown. Confirm current model and region availability
in your own subscription first.

### Go LIVE

```bash
cp .env.example .env               # then fill in the endpoints from the deployment
az login
streamlit run app.py
```

Keyless needs endpoints only, never a secret:

| Demo | Env |
|---|---|
| Thinking-1 | `MAI_FOUNDRY_ENDPOINT`, `MAI_THINKING_DEPLOYMENT` |
| Image-2.5 / Flash | `MAI_IMAGE_ENDPOINT`, deployment names |
| Transcribe-1.5 | `MAI_SPEECH_ENDPOINT` |
| Voice-2 (TTS) | `MAI_SPEECH_ENDPOINT`, `MAI_SPEECH_RESOURCE_ID` |

Chat, image, and speech are configured independently, which is what lets Image point at
a different resource when regional availability requires it. All of them can also point
at the same account.

To use resource keys instead, set `MAI_AUTH_MODE=key` and fill in `MAI_*_API_KEY` and
`MAI_SPEECH_KEY`. That path needs an account deployed with `disableLocalAuth = false`.

### Verify

```bash
MAI_EXECUTION_MODE=strict python scripts/live_smoke.py
```

The script calls all four services and fails loudly rather than degrading, which is
exactly what you want before walking on stage. `MAI_EXECUTION_MODE=demo`, the default,
degrades a failed live call to a labelled fallback instead.

## Guidance

### How the models are called

Two service surfaces, both over plain HTTPS with `requests`, matching the Microsoft REST
documentation one-to-one with no SDK coupling:

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

### Authentication

Keyless is the default. The two service families use different token audiences, which is
the detail that most often costs an afternoon:

| Service | Scope | Role |
|---|---|---|
| Thinking, Image | `https://ai.azure.com/.default` | Cognitive Services User |
| Transcribe, Voice | `https://cognitiveservices.azure.com/.default` | Cognitive Services Speech User |

Speech additionally requires a custom subdomain on the resource, and keyless text to
speech requires the resource ID, because that path takes the token as
`aad#<resourceId>#<token>`. Full details and sources are in section 0 of
[`docs/API_VERIFIED.md`](docs/API_VERIFIED.md).

If a demo shows FALLBACK when you expected LIVE, see the checklist in
[SUPPORT.md](SUPPORT.md). Role assignments take up to five minutes to propagate.

### Costs

The demos are deliberately small: short prompts, one image per run, a few seconds of
audio. The recurring cost is the deployed capacity rather than the calls, so tear the
resource group down when you are done. Current prices are on the
[Azure pricing page](https://azure.microsoft.com/pricing/details/ai-foundry/); this
repository does not estimate them, because they change.

### Notes on the MAI lineup

All of these are recorded, with sources, in [`docs/API_VERIFIED.md`](docs/API_VERIFIED.md):

- **Preview status.** Microsoft Learn currently labels MAI-Thinking-1 and the selected
  Image, Transcribe, and Voice capabilities as preview. Preview capabilities can change.
- **Transcribe naming.** This sample uses the currently documented `mai-transcribe-1.5`
  identifier rather than names from older materials.
- **Deployment names are configurable.** The `model` field in each call is the deployment
  name you assign, not a fixed model ID.
- **Voice styles are voice-dependent.** `empathy` exists on `es-ES-Marta` and the
  multilingual voices, not on the en-US voices, which offer `excited`, `hopeful`,
  `softvoice` and others. The app validates the requested style against the voice and
  falls back to the closest supported one.

### Development

```bash
pip install ruff pytest
ruff check .
ruff format --check .
pytest
```

The suite is fully offline and hermetic: no credentials, no network, and no dependence
on who is signed in to Azure. CI runs the same checks on Python 3.11 and 3.13, plus
Microsoft Security DevOps for credential and template scanning, on every push and pull
request. See [CONTRIBUTING.md](CONTRIBUTING.md).

```
app.py                     Streamlit entry (4 main tabs + 2 backup tabs)
mai/                       Shared client library
  auth.py                  Microsoft Entra ID tokens, per audience
  config.py                Env config, endpoints, voice/style registry
  client.py                MAIClient, pluggable LIVE + FALLBACK for all 4 families
  ssml.py                  SSML builder + style validation
  fallback.py              Deterministic offline stand-ins
demos/                     One module per demo (each exposes render(client))
assets/data/               cloud_estate.json, region_capacity.json (Thinking demo)
docs/
  API_VERIFIED.md          Verified API surface, with sources
  PROMPTS.md               Every demo prompt, ready to copy and paste
  IMAGE_PRESERVATION.md    What the image edit actually preserved, measured
scripts/
  live_smoke.py            Strict preflight against all four services
  measure_preservation.py  Reproduces the numbers in IMAGE_PRESERVATION.md
tests/                     Offline tests (pytest, no credentials)
infra/                     Bicep: Foundry resource, model deployments, role assignments
```

## Resources

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [SUPPORT.md](SUPPORT.md), and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Licensed under the MIT License; see
[LICENSE.md](LICENSE.md).

## Trademarks

This project may contain trademarks or logos for projects, products, or services.
Authorized use of Microsoft trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause
confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos is
subject to those third parties' policies.
