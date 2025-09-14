param location string
param cosmosAccountName string
param databaseName string = 'VisionaryLabDB'
param containerName string = 'visionarylab'
param deployNew bool = true
param subnetId string = ''
// Control public access. Set to 'Enabled' for public Internet access, 'Disabled' for private-only
param publicNetworkAccess string = 'Enabled'

// Create a unique name if not provided
var uniqueCosmosAccountName = cosmosAccountName == '' ? 'cosmos-${uniqueString(resourceGroup().id)}' : cosmosAccountName

// Cosmos DB Account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = if (deployNew) {
  name: uniqueCosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: false
    // Control public access
    publicNetworkAccess: publicNetworkAccess
    // Do not bypass network ACLs via trusted Azure services when PNA is disabled
    networkAclBypass: 'None'
    // With Private Endpoint, VNet filters are not required
    isVirtualNetworkFilterEnabled: false
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: []
    virtualNetworkRules: []
  }
}

// SQL Database
resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = if (deployNew) {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Container: visionarylab
resource visionarylabContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = if (deployNew) {
  parent: sqlDatabase
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          '/media_type'
        ]
        kind: 'Hash'
        version: 1 // Non-hierarchical partition key
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/_etag/?'
          }
        ]
      }
    }
    options: {
      throughput: 600
    }
  }
}

// SQL Role Definition - Data Reader
resource dataReaderRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-05-15' = if (deployNew) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, 'sql-role-definition-reader')
  properties: {
    roleName: '${uniqueCosmosAccountName}-data-reader-role'
    type: 'CustomRole'
    assignableScopes: [
      cosmosAccount.id
    ]
    permissions: [
      {
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/read'
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/executeQuery'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/readChangeFeed'
        ]
      }
    ]
  }
}

// SQL Role Definition - Data Contributor
resource dataContributorRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-05-15' = if (deployNew) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, 'sql-role-definition-contributor')
  properties: {
    roleName: '${uniqueCosmosAccountName}-data-contributor-role'
    type: 'CustomRole'
    assignableScopes: [
      cosmosAccount.id
    ]
    permissions: [
      {
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*'
        ]
      }
    ]
  }
}

// Outputs
output cosmosAccountId string = cosmosAccount.id
output cosmosAccountName string = cosmosAccount.name
output cosmosAccountEndpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = sqlDatabase.name
output containerName string = visionarylabContainer.name
output systemAssignedIdentityPrincipalId string = cosmosAccount.identity.principalId
output dataReaderRoleId string = dataReaderRole.id
output dataContributorRoleId string = dataContributorRole.id
