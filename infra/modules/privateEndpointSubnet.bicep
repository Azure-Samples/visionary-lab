param location string
param vnetName string
@description('Subnet name for Private Endpoints')
param privateEndpointSubnetName string = 'private-endpoints'
@description('Address prefix for the Private Endpoints subnet')
param privateEndpointSubnetAddressPrefix string = '10.0.2.0/24'
@description('Whether to create a new Private Endpoint subnet (false to reuse existing)')
param deployNew bool = true
@description('Optional: existing Private Endpoint subnet ID when deployNew is false')
param existingPrivateEndpointSubnetId string = ''

// Reference existing VNet (created elsewhere)
resource vNet 'Microsoft.Network/virtualNetworks@2023-09-01' existing = {
  name: vnetName
}

// Dedicated subnet for Private Endpoints
resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-09-01' = if (deployNew) {
  parent: vNet
  name: privateEndpointSubnetName
  properties: {
    addressPrefix: privateEndpointSubnetAddressPrefix
    // Required for Private Endpoints
    privateEndpointNetworkPolicies: 'Disabled'
    privateLinkServiceNetworkPolicies: 'Disabled'
  }
}

// Existing reference when not deploying new
resource existingPeSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-09-01' existing = if (!deployNew && length(existingPrivateEndpointSubnetId) == 0) {
  parent: vNet
  name: privateEndpointSubnetName
}

output privateEndpointSubnetId string = deployNew ? privateEndpointSubnet.id : (length(existingPrivateEndpointSubnetId) > 0 ? existingPrivateEndpointSubnetId : existingPeSubnet.id)
output privateEndpointSubnetName string = deployNew ? privateEndpointSubnet.name : (length(existingPrivateEndpointSubnetId) > 0 ? last(split(existingPrivateEndpointSubnetId, '/')) : existingPeSubnet.name)
