param location string
param vnetName string
@description('Subnet name for Private Endpoints')
param privateEndpointSubnetName string = 'private-endpoints'
@description('Address prefix for the Private Endpoints subnet')
param privateEndpointSubnetAddressPrefix string = '10.0.2.0/24'

// Reference existing VNet (created elsewhere)
resource vNet 'Microsoft.Network/virtualNetworks@2023-09-01' existing = {
  name: vnetName
}

// Dedicated subnet for Private Endpoints
resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-09-01' = {
  parent: vNet
  name: privateEndpointSubnetName
  properties: {
    addressPrefix: privateEndpointSubnetAddressPrefix
    // Required for Private Endpoints
    privateEndpointNetworkPolicies: 'Disabled'
    privateLinkServiceNetworkPolicies: 'Disabled'
  }
}

output privateEndpointSubnetId string = privateEndpointSubnet.id
output privateEndpointSubnetName string = privateEndpointSubnet.name

