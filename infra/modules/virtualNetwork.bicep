param location string
param vnetName string
param vnetAddressSpace string = '10.0.0.0/16'
param subnetName string = 'infrastructure-subnet'
param subnetAddressPrefix string = '10.0.0.0/23'
param deployNew bool = true
// When reusing an existing VNet/subnet, set deployNew=false and pass IDs or names
@description('Optional: existing VNet resource ID when deployNew is false')
param existingVnetId string = ''
@description('Optional: existing subnet resource ID when deployNew is false')
param existingSubnetId string = ''

// Virtual Network
resource vNet 'Microsoft.Network/virtualNetworks@2023-09-01' = if (deployNew) {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressSpace
      ]
    }
  }
}

// Existing references when not deploying new
resource existingVNet 'Microsoft.Network/virtualNetworks@2023-09-01' existing = if (!deployNew && length(existingVnetId) == 0) {
  name: vnetName
}

resource existingSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-09-01' existing = if (!deployNew && length(existingSubnetId) == 0) {
  parent: existingVNet
  name: subnetName
}

// Subnet for Container Apps infrastructure
// Container Apps requires a NON-delegated subnet for infrastructure
resource subnet 'Microsoft.Network/virtualNetworks/subnets@2023-09-01' = if (deployNew) {
  parent: vNet
  name: subnetName
  properties: {
    addressPrefix: subnetAddressPrefix
    // No delegation for Container Apps infrastructure subnet
    // No service endpoints; we use Private Endpoints for Cosmos DB
  }
}

// Outputs
output vnetId string = deployNew ? vNet.id : (length(existingVnetId) > 0 ? existingVnetId : existingVNet.id)
output vnetName string = deployNew ? vNet.name : (length(existingVnetId) > 0 ? last(split(existingVnetId, '/')) : existingVNet.name)
output subnetId string = deployNew ? subnet.id : (length(existingSubnetId) > 0 ? existingSubnetId : existingSubnet.id)
output subnetName string = deployNew ? subnet.name : (length(existingSubnetId) > 0 ? last(split(existingSubnetId, '/')) : existingSubnet.name)
