using 'main.bicep'

// Must be globally unique — it becomes the custom subdomain
// (<accountName>.services.ai.azure.com / .cognitiveservices.azure.com).
param accountName = 'mai-foundry-demos-<your-suffix>'
param location = 'eastus'
param deployImageModels = true

// Who gets to call the models. Your own object ID:
//   az ad signed-in-user show --query id -o tsv
// Leave empty to deploy without granting anyone access, then assign the roles
// separately. Use principalType = 'ServicePrincipal' for a managed identity.
param principalId = ''
param principalType = 'User'

// Keyless by default: Microsoft Entra ID is the only way in and the account has
// no usable keys. Set to false only if you need MAI_AUTH_MODE=key.
param disableLocalAuth = true

param tags = {
  project: 'mai-foundry-demos'
}
