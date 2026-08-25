using 'main.bicep'

// Must be globally unique — it becomes the custom subdomain
// (<accountName>.services.ai.azure.com / .cognitiveservices.azure.com).
param accountName = 'mai-foundry-demos-<your-suffix>'
param location = 'eastus'
param deployImageModels = true

param tags = {
  project: 'mai-foundry-demos'
}
