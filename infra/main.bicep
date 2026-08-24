// Deploys one Microsoft Foundry resource (Microsoft.CognitiveServices/accounts,
// kind AIServices) with MAI-Thinking-1 and the MAI image models, mirroring the
// setup this repo's demos actually run against.
//
// Verified against Microsoft Learn (2026-08): api-version 2025-09-01 for both
// `accounts` and `accounts/deployments`.
//   https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/2025-09-01/accounts
//   https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/2025-09-01/accounts/deployments
//
// Transcribe-1.5 and Voice-2 need NO separate deployment — they're called through
// this same account's Speech endpoints (see docs/API_VERIFIED.md).

@description('Name of the Foundry (Cognitive Services / AIServices) account. Also used as the custom subdomain, so it must be globally unique.')
param accountName string

@description('Deploy MAI-Image-2.5 and MAI-Image-2.5-Flash on this account. MAI image models are only available in a subset of regions (see `location`) — set this to false to deploy Thinking-1 only in a region without image support.')
param deployImageModels bool = true

@description('Azure region for the account. The default allowed list is the set of regions that currently support MAI image models; if deployImageModels=false you can widen this to any Foundry region.')
@allowed([
  'eastus'
  'westus'
  'westcentralus'
  'westeurope'
  'swedencentral'
  'southindia'
  'uaenorth'
])
param location string = 'eastus'

@description('Global Standard TPM/capacity for the MAI-Thinking-1 deployment.')
param thinkingCapacity int = 50

@description('Global Standard capacity for each MAI image deployment.')
param imageCapacity int = 1

@description('Tags applied to the account.')
param tags object = {}

// Model versions verified against a real deployment in this repo's Foundry
// resource on 2026-08-13 (see docs/API_VERIFIED.md). Foundry defaults to the
// latest version when omitted, but pinning keeps this template reproducible.
var thinkingModelVersion = '2026-06-01'
var imageModelVersion = '2026-06-02'

resource account 'Microsoft.CognitiveServices/accounts@2025-09-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  tags: tags
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false // demos authenticate with an api-key; flip to true + use Entra ID for production
    allowProjectManagement: true // enables a Foundry project on this account, e.g. `proj-<name>`
  }
}

resource thinkingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-09-01' = {
  parent: account
  name: 'MAI-Thinking-1'
  sku: {
    name: 'GlobalStandard'
    capacity: thinkingCapacity
  }
  properties: {
    model: {
      format: 'Microsoft'
      name: 'MAI-Thinking-1'
      version: thinkingModelVersion
    }
  }
}

// Cognitive Services deployments on the same account must be created one at a
// time — concurrent PUTs on sibling `deployments` resources are unreliable and
// commonly fail. The explicit `dependsOn` chain below serializes them; without
// it, Bicep would happily try to create both image deployments in parallel.
resource imageEditDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-09-01' = if (deployImageModels) {
  parent: account
  name: 'MAI-Image-2.5'
  sku: {
    name: 'GlobalStandard'
    capacity: imageCapacity
  }
  properties: {
    model: {
      format: 'Microsoft'
      name: 'MAI-Image-2.5'
      version: imageModelVersion
    }
  }
  dependsOn: [
    thinkingDeployment
  ]
}

resource imageFlashDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-09-01' = if (deployImageModels) {
  parent: account
  name: 'MAI-Image-2.5-Flash'
  sku: {
    name: 'GlobalStandard'
    capacity: imageCapacity
  }
  properties: {
    model: {
      format: 'Microsoft'
      name: 'MAI-Image-2.5-Flash'
      version: imageModelVersion
    }
  }
  dependsOn: [
    imageEditDeployment
  ]
}

@description('Base endpoint for MAI-Thinking-1 (OpenAI-compatible chat completions) and, if deployed, the MAI image APIs. Maps to MAI_FOUNDRY_ENDPOINT / MAI_IMAGE_ENDPOINT in .env.')
output foundryEndpoint string = account.properties.endpoint

@description('Speech endpoint for MAI-Transcribe-1.5. Maps to MAI_SPEECH_ENDPOINT in .env.')
output speechEndpoint string = 'https://${accountName}.cognitiveservices.azure.com'

@description('Region to use as MAI_SPEECH_REGION (the *.tts.speech.microsoft.com host for MAI-Voice-2).')
output speechRegion string = location

@description('Account name — fetch keys with: az cognitiveservices account keys list --name <this> --resource-group <rg>')
output accountName string = account.name
