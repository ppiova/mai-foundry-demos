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

Each model deployment is created in sequence; actual deployment duration varies.

## Access model

The template deploys **keyless by default**: `disableLocalAuth` is `true`, so the
account issues no usable keys and Microsoft Entra ID is the only way in. Access
comes from two role assignments on the account, scoped to `principalId`:

| Role | Grants |
|---|---|
| `Cognitive Services User` | MAI-Thinking-1 and the MAI image APIs |
| `Cognitive Services Speech User` | MAI-Transcribe-1.5 and MAI-Voice-2 |

`customSubDomainName` is set because the Speech APIs reject Entra tokens on
regional endpoints. That property cannot be changed after creation.

Role assignments can take up to five minutes to propagate. If the app reports
FALLBACK right after deployment, wait and retry before assuming a misconfiguration.

To use keys instead, deploy with `disableLocalAuth = false` and set
`MAI_AUTH_MODE=key`.

## Region constraints

Model and deployment availability changes over time and can differ by subscription.
Check the current Microsoft Foundry model catalog before setting `location`. If you
only need Thinking, set `deployImageModels = false`; the app can independently point
`MAI_IMAGE_*` at another authorized resource.

## Quota

`thinkingCapacity` draws from your subscription's **Tokens-per-Minute (thousands)**
quota for `MAI-Thinking-1` in the target region — this is a per-subscription,
per-region limit, separate from the account itself. If `az deployment group
validate` (or the real deployment) fails with `InsufficientQuota`, you're not
looking at a template bug: either lower `thinkingCapacity`, delete/shrink an
existing `MAI-Thinking-1` deployment in that region, or request more quota:
https://aka.ms/oai/stuquotarequest. An earlier authorized
`az deployment group validate` run checked the Azure deployment/schema contract;
that command was not an end-to-end deployment or a live model endpoint test. No live
endpoint verification was performed for PR #4.

## After deploying: fill in `.env`

Keyless needs no secret at all, only endpoints. Copy `.env.example` to `.env` from
the repo root and fill it from the deployment outputs:

| Output | `.env` variable |
|---|---|
| `foundryEndpoint` | `MAI_FOUNDRY_ENDPOINT`, `MAI_IMAGE_ENDPOINT` |
| `speechEndpoint` | `MAI_SPEECH_ENDPOINT` |
| `speechResourceId` | `MAI_SPEECH_RESOURCE_ID` (keyless MAI-Voice-2 only) |

All of them can point at the **same** account. Then sign in locally:

```bash
az login
```

`MAI_*_API_KEY` and `MAI_SPEECH_KEY` stay empty. They are read only when
`MAI_AUTH_MODE=key`, which needs an account deployed with
`disableLocalAuth = false`.

## Tear down

```bash
az group delete --name rg-mai-examples --yes --no-wait
```
