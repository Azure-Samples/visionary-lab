// Reusable module for deploying a model under an AI Foundry resource

@description('Name of the parent AI Foundry resource')
param aiFoundryName string

@description('Deployment name (used to reference the model in API calls)')
param deploymentName string

@description('Model name (e.g., gpt-4o or gpt-image-1.5)')
param modelName string

@description('Model format')
param modelFormat string = 'OpenAI'

@description('Model version')
param modelVersion string

@description('SKU name for the deployment')
param skuName string = 'GlobalStandard'

@description('SKU capacity (throughput units)')
param skuCapacity int = 1

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: aiFoundryName
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: deploymentName
  sku: {
    capacity: skuCapacity
    name: skuName
  }
  properties: {
    model: {
      name: modelName
      format: modelFormat
      version: modelVersion
    }
  }
}

output deploymentName string = modelDeployment.name
output deploymentId string = modelDeployment.id
