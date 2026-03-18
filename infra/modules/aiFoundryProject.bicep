// AI Foundry Project — groups inputs/outputs for a single use case
// Projects are child resources of the AI Foundry account

@description('Name of the AI Foundry project')
param aiProjectName string

@description('Name of the parent AI Foundry resource')
param aiFoundryName string

@description('Location for the project')
param location string

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: aiFoundryName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  name: aiProjectName
  parent: aiFoundry
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

output projectName string = aiProject.name
output projectId string = aiProject.id
