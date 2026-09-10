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

@description('Deploy MAI-Image-2.5 and MAI-Image-2.5-Flash on this account. Confirm current model availability for `location`; set this to false for a Thinking-only deployment.')
param deployImageModels bool = true

@description('Azure region for the account. Confirm current model and deployment availability in Microsoft Foundry before deployment.')
param location string = 'eastus'

@description('Global Standard TPM/capacity for the MAI-Thinking-1 deployment.')
param thinkingCapacity int = 50

@description('Global Standard capacity for each MAI image deployment.')
param imageCapacity int = 1

@description('Tags applied to the account.')
param tags object = {}

@description('Object ID of the identity that will call the models: your own user (az ad signed-in-user show --query id -o tsv) or the app\'s managed identity. Leave empty to skip the role assignments and grant access separately.')
param principalId string = ''

@description('Type of `principalId`. Set to ServicePrincipal for a managed identity, which also avoids a replication delay failing the deployment.')
@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
param principalType string = 'User'

@description('Disable key-based authentication, leaving Microsoft Entra ID as the only way in. Keyless is the default posture for this sample; set to false only if you specifically need MAI_AUTH_MODE=key.')
param disableLocalAuth bool = true

// Model versions verified against a real deployment in this repo's Foundry
// resource during an earlier authorized live check (see docs/API_VERIFIED.md). Foundry defaults to the
// latest version when omitted, but pinning keeps this template reproducible.
var thinkingModelVersion = '2026-06-01'
var imageModelVersion = '2026-06-02'

// Built-in role definition IDs, resolved from the live directory on 2026-09-10 with
//   az role definition list --name "<role>" --query "[0].name" -o tsv
// The account is a multi-service AIServices resource, so it needs both: model
// inference (Thinking, Image) is governed by Cognitive Services User, and the
// Speech APIs (Transcribe, Voice) by Cognitive Services Speech User.
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var speechUserRoleId = 'f2dc8367-1007-4938-bd23-fe263f013447'
var assignRoles = !empty(principalId)

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
    // Required for Microsoft Entra authentication against the Speech APIs, which
    // reject tokens on the regional endpoints. Not reversible once set.
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: disableLocalAuth
    allowProjectManagement: true // enables a Foundry project on this account, e.g. `proj-<name>`
  }
}

// Model inference: MAI-Thinking-1 and the MAI image APIs.
resource inferenceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignRoles) {
  scope: account
  name: guid(account.id, principalId, cognitiveServicesUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      cognitiveServicesUserRoleId
    )
    principalId: principalId
    principalType: principalType
  }
}

// Speech APIs: MAI-Transcribe-1.5 and MAI-Voice-2.
resource speechRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignRoles) {
  scope: account
  name: guid(account.id, principalId, speechUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      speechUserRoleId
    )
    principalId: principalId
    principalType: principalType
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

@description('Region to use as MAI_SPEECH_REGION (the *.tts.speech.microsoft.com host used only when MAI_AUTH_MODE=key).')
output speechRegion string = location

@description('ARM resource ID of the account. Maps to MAI_SPEECH_RESOURCE_ID in .env, which keyless MAI-Voice-2 requires (the token is sent as aad#<resourceId>#<token>).')
output speechResourceId string = account.id

@description('Account name. With disableLocalAuth left at true there are no keys to fetch: access is granted by the role assignments above.')
output accountName string = account.name
