param cosmosAccountName string
param containerAppPrincipalId string
param dataContributorRoleId string

// Reference existing Cosmos DB account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

// SQL Role Assignment for Container App
resource containerAppRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, containerAppPrincipalId, 'container-app-assignment')
  properties: {
    principalId: containerAppPrincipalId
    roleDefinitionId: dataContributorRoleId
    scope: cosmosAccount.id
  }
}

output roleAssignmentId string = containerAppRoleAssignment.id