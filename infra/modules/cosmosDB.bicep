param location string
param cosmosAccountName string
param databaseName string = 'VisionaryLabDB'
param containerName string = 'visionarylab'
param deployNew bool = true

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
    enableFreeTier: true
    publicNetworkAccess: 'Enabled'
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
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    capacity: {
      totalThroughputLimit: 1000
    }
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
      // Add computed properties if needed
      // computedProperties: [
      //   {
      //     name: 'computed_property_name'
      //     query: 'query_to_compute_property'
      //   }
      // ]
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
output primaryKey string = cosmosAccount.listKeys().primaryMasterKey
