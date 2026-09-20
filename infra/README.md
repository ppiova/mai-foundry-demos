# Infrastructure as code

`main.bicep` deploys one **Microsoft Foundry** resource (`Microsoft.CognitiveServices/accounts`,
kind `AIServices`) with configurable `MAI-Thinking-1`, `MAI-Image-2.5`, and
`MAI-Image-2.5-Flash` deployments. The template was checked against
Microsoft Learn's Bicep reference (api-version `2025-09-01`) and the official
[Azure Verified Module for Cognitive Services accounts](https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/cognitive-services/account).

`MAI-Transcribe-1.5` and `MAI-Voice-2` need **no separate deployment** — the app
calls them through this same account's Speech endpoints. See
[`docs/API_VERIFIED.md`](../docs/API_VERIFIED.md) for the full API surface.

## Deploy

**Optional LIVE path only.** The [Thinking workshop](../docs/THINKING_WORKSHOP.md)
needs none of these resources. These commands provision infrastructure; the
workshop's migration-plan validator does not provision, move, or delete anything.
Review availability, permissions, quota, and [costs](../README.md#costs) first.
Run these examples from the `infra` directory. The shell must be signed in to the
intended subscription, and the caller needs permission to create the resources
and role assignments.

**Bash:**

```bash
# 1. Create (or pick) a resource group after checking current model availability.
az group create --name rg-mai-examples --location eastus

# 2. Edit main.bicepparam (accountName must be globally unique) and set
#    principalId to whoever will call the models:
#      az ad signed-in-user show --query id -o tsv

# 3. Deploy.
az deployment group create \
  --resource-group rg-mai-examples \
  --template-file main.bicep \
  --parameters main.bicepparam
```

**PowerShell:**

```powershell
az group create --name rg-mai-examples --location eastus
# Edit main.bicepparam and set principalId before deploying.
# az ad signed-in-user show --query id -o tsv
az deployment group create `
  --resource-group rg-mai-examples `
  --template-file main.bicep `
  --parameters main.bicepparam
```

Each model deployment is created in sequence; actual deployment duration varies.

## Access model

The template deploys **keyless by default**: `disableLocalAuth` is `true`, so the
account issues no usable keys and Microsoft Entra ID is the only way in. Access
comes from two role assignments on the account, scoped to `principalId`:

| Role | Grants |
|---|---|
| `Cognitive Services User` | MAI-Thinking-1 and the MAI image APIs |
| `Cognitive Services Speech User` | MAI-Transcribe-1.5 and MAI-Voice-2 |

`customSubDomainName` is set because it is a prerequisite for Speech Entra
eligibility. Transcription uses that custom host, but TTS uses
`https://<region>.tts.speech.microsoft.com/cognitiveservices/v1` in **both** auth
modes. Keyless TTS wraps its token as `aad#<resourceId>#<token>`. The custom
subdomain cannot be changed after creation. See the dated verification record in
[`docs/API_VERIFIED.md`](../docs/API_VERIFIED.md).

Role assignments can take up to five minutes to propagate. If the app reports
FALLBACK right after deployment, wait and retry before assuming a misconfiguration.

To use keys instead, deploy with `disableLocalAuth = false` and set
`MAI_AUTH_MODE=key`.

## Region constraints

Model and deployment availability changes over time and can differ by subscription.
Check the current Microsoft Foundry model catalog before setting `location`. If you
only need Thinking, set `deployImageModels = false`; the app can independently point
`MAI_IMAGE_*` at another authorized resource.

### Speech is the constraint that fails quietly

Thinking and Image fail loudly when a region cannot serve them: the deployment
errors. Speech does not. `MAI_SPEECH_ENDPOINT` on a resource in the wrong region
simply never transcribes, and the demo shows FALLBACK with no obvious cause.

Verified against [Speech service regions](https://learn.microsoft.com/azure/ai-services/speech-service/regions?tabs=llmspeech)
on 2026-09-10:

| Capability | Regions |
|---|---|
| MAI-Transcribe (LLM speech) | `centralindia`, `eastus`, `northeurope`, `southeastasia`, `westus`, `westus2` |
| MAI voices (Voice-2 TTS) | `canadacentral`, `centralindia`, `eastus`, `eastus2`, `francecentral`, `southeastasia`, `swedencentral`, `westeurope`, `westus2` |

**Four regions serve both**, and those are the only ones where a single account
could run all four demos in that dated Speech snapshot:
`centralindia`, `eastus`, `southeastasia`, `westus2`. This is necessary, not
sufficient: separately check Thinking/Image availability and quota, and recheck
the region documentation before a LIVE run.

Two traps worth naming:

- `westeurope` and `swedencentral` have MAI voices but **not** MAI-Transcribe.
  Both are plausible Foundry regions, and picking one silently costs you the
  transcription demo.
- `southindia` and `spaincentral` are valid for an `AIServices` resource and are
  documented as **not supported for speech processing at all**. `southindia` in
  particular appears in the image-model region guidance, so it is an easy choice
  to make for the wrong reason.

Speech and the Foundry models do not have to share an account. Point
`MAI_SPEECH_*` at a resource in one of the four, and `MAI_FOUNDRY_*` /
`MAI_IMAGE_*` wherever the models you want are available.

## Quota

`thinkingCapacity` draws from your subscription's **Tokens-per-Minute (thousands)**
quota for `MAI-Thinking-1`. Verified live on 2026-09-11: that quota is allocated
**per subscription, not per region** (`az cognitiveservices usage list` reports it
with `scopeType: Global`). Most models are region-scoped instead; do not assume
switching `location` frees any headroom for this one.

If `az deployment group validate` (or the real deployment) fails with
`InsufficientQuota`, check what actually holds it before assuming a stale
deployment is the cause, since a live check of this subscription found the quota
fully committed with **no deployment anywhere holding it**:

```bash
az cognitiveservices usage list --location <any-region-in-the-subscription> \
  --query "[?contains(name.value, 'MAI-Thinking-1')]"
```

If `currentValue` equals `limit`, lowering `thinkingCapacity` will not help; even
`thinkingCapacity = 1` fails identically once the quota is fully committed. Two
ways forward: request more quota (https://aka.ms/oai/stuquotarequest), or deploy
with `deployThinkingModel = false` to bring up Image and Speech independently
while the request is pending. Nothing else in the app depends on all four
services being live at once; each is checked and degrades on its own.

`thinkingCapacity` and `imageCapacity` configure **Global Standard** throughput,
not reserved PTUs. Quota availability is not a cost estimate. Standard usage and
Provisioned reserved-capacity billing are different models; see
[deployment types](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/deployment-types)
and the [per-service pricing links](../README.md#costs). Also, `GlobalStandard`
describes global inference routing: the account's location is not a promise that
Foundry model processing remains in that region.

## After deploying: fill in `.env`

Keyless needs no secret, but it does need endpoints and resource metadata. Copy
`.env.example` to `.env` from the repo root if it does not already exist, and fill
the configuration from the deployment outputs:

| Output | `.env` variable |
|---|---|
| `foundryEndpoint` | `MAI_FOUNDRY_ENDPOINT`, `MAI_IMAGE_ENDPOINT` |
| `speechEndpoint` | `MAI_SPEECH_ENDPOINT` |
| `speechRegion` | `MAI_SPEECH_REGION` (regional TTS host, **both** auth modes) |
| `speechResourceId` | `MAI_SPEECH_RESOURCE_ID` (keyless MAI-Voice-2 only) |

All of them can point at the **same** account where all selected services are
supported. If a model deployment was disabled, leave that service's endpoint
unconfigured instead of interpreting the account output as proof it exists.
Then sign in locally:

```bash
az login
```

For a keyless-only run, `MAI_*_API_KEY` and `MAI_SPEECH_KEY` must stay empty in
both `.env` and the process environment. The client can use configured keys in
`MAI_AUTH_MODE=entra` too: they are a per-service safety net when Entra token
acquisition fails, or when that service's keyless prerequisites are absent.
That safety net still needs an account with `disableLocalAuth = false`.
It does not turn a resource-key result into evidence of keyless success, and
`MAI_EXECUTION_MODE=strict` does not disable it.

Use the [Bash/PowerShell LIVE startup and preflight](../README.md#go-live)
instructions, with a fresh terminal after an offline rehearsal. Check final
result provenance and any authentication-fallback warning. Thinking keyless
live success was **not** established by the 2026-09-11 check: quota blocked it;
consult the verification matrix rather than inferring success from other services.

## Tear down

No cleanup is needed for an offline workshop. For a LIVE run, stop the app to
stop new calls, review actual usage, and remove only resources you created for
the demo. **The following deletes the entire resource group and everything in
it.** Confirm the selected subscription and ensure the group contains no shared
or important resources; do not run it against an existing shared group.

```bash
az group delete --name rg-mai-examples
```

The same command works in PowerShell. Keep the confirmation prompt; resource
deletion is not a substitute for reviewing already-incurred charges.
