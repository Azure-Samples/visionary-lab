// Role assignment: Foundry User on AI Foundry resource
// Allows the Container App identity to call OpenAI and provider-model APIs.

@description('Resource ID of the AI Foundry resource')
param aiFoundryId string

@description('Principal ID of the Container App managed identity')
param containerAppPrincipalId string

// Foundry User role definition ID
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource aiFoundryRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiFoundryId, containerAppPrincipalId, foundryUserRoleId)
  scope: aiFoundryResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
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
