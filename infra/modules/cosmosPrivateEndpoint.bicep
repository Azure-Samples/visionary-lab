param location string
@description('Cosmos DB account resource ID')
param cosmosAccountId string
@description('Subnet ID for the Private Endpoint')
param subnetId string
@description('Private DNS zone ID for Cosmos DB (privatelink.documents.azure.com)')
param privateDnsZoneId string

// Reference the Cosmos DB account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  scope: resourceGroup()
  name: last(split(cosmosAccountId, '/'))
}

// Private Endpoint to Cosmos DB (SQL API subresource)
resource pe 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: 'pe-cosmos'
  location: location
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'cosmosdb-pls'
        properties: {
          privateLinkServiceId: cosmosAccountId
          groupIds: [ 'Sql' ]
          requestMessage: 'Private Endpoint for Container Apps -> Cosmos DB'
        }
      }
    ]
  }
}

// Attach Private DNS zone group so the A record is created in the zone
resource peZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2020-05-01' = {
  name: 'cosmosdb-private-dns'
  parent: pe
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'documents'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

output privateEndpointId string = pe.id

