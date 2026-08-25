// AI Foundry resource (Microsoft.CognitiveServices/accounts kind 'AIServices')
// This replaces the separate Azure OpenAI resources with a single unified AI Foundry resource

@description('Name of the AI Foundry resource')
param aiFoundryName string

@description('Location for the AI Foundry resource')
param location string

@description('Deploy a new AI Foundry resource or reference an existing one')
param deployNew bool = true

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = if (deployNew) {
  name: aiFoundryName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiFoundryName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource existingAiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (!deployNew) {
  name: aiFoundryName
}

output aiFoundryEndpoint string = deployNew ? aiFoundry.properties.endpoint : existingAiFoundry.properties.endpoint
output aiFoundryName string = aiFoundryName
output aiFoundryId string = deployNew ? aiFoundry.id : existingAiFoundry.id
output aiFoundryPrincipalId string = deployNew ? aiFoundry.identity.principalId : ''
