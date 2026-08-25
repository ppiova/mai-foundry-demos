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

# 2. Edit main.bicepparam — accountName must be globally unique.

# 3. Deploy.
az deployment group create \
  --resource-group rg-mai-examples \
  --template-file main.bicep \
  --parameters main.bicepparam
```

Each model deployment is created in sequence; actual deployment duration varies.

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
https://aka.ms/oai/stuquotarequest. This template was validated end-to-end
against a live Azure subscription (`az deployment group validate`) — it passed
every schema and property check; the only rejection we hit while testing was
this exact quota limit, not the template.

## After deploying: fill in `.env`

The deployment outputs the endpoints; you still need to fetch keys separately
(Bicep never outputs secrets):

```bash
az cognitiveservices account keys list \
  --name <accountName> --resource-group rg-mai-examples \
  --query key1 -o tsv
```

Then, from the repo root:

```bash
copy .env.example .env
```

and fill in `MAI_FOUNDRY_ENDPOINT` / `MAI_FOUNDRY_API_KEY` (and `MAI_IMAGE_*`,
`MAI_SPEECH_*`) with the `foundryEndpoint` / `speechEndpoint` outputs and the
key above. All four can point at the **same** account.

## Tear down

```bash
az group delete --name rg-mai-examples --yes --no-wait
```
