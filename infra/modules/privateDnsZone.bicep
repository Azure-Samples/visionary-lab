@description('ID of the VNet to link the private DNS zone to')
param vnetId string
@description('Name of the private DNS zone')
param privateDnsZoneName string = 'privatelink.documents.azure.com'
@description('Name for the VNet link to the private DNS zone')
param vnetLinkName string = 'vnet-link'

// Private DNS Zone for Cosmos DB Private Link
resource privateDnsZone 'Microsoft.Network/privateDnsZones@2018-09-01' = {
  name: privateDnsZoneName
  location: 'global'
}

// Link the VNet used by Container Apps to the private DNS zone
resource vnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2018-09-01' = {
  name: vnetLinkName
  parent: privateDnsZone
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}

output privateDnsZoneId string = privateDnsZone.id
