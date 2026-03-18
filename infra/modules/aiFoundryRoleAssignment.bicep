// Role assignment: Cognitive Services OpenAI User on AI Foundry resource
// Allows the Container App managed identity to call OpenAI APIs via the Foundry

@description('Resource ID of the AI Foundry resource')
param aiFoundryId string

@description('Principal ID of the Container App managed identity')
param containerAppPrincipalId string

// Cognitive Services OpenAI User role definition ID
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource aiFoundryRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiFoundryId, containerAppPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: aiFoundryResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalId: containerAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Reference the existing AI Foundry to scope the role assignment
@description('Name of the AI Foundry resource')
param aiFoundryName string

resource aiFoundryResource 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: aiFoundryName
}

output roleAssignmentId string = aiFoundryRoleAssignment.id
