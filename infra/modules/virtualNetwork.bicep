param location string
param vnetName string
param vnetAddressSpace string = '10.0.0.0/16'
param subnetName string = 'infrastructure-subnet'
param subnetAddressPrefix string = '10.0.0.0/23'
param deployNew bool = true

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
output vnetId string = deployNew ? vNet.id : ''
output vnetName string = deployNew ? vNet.name : vnetName
output subnetId string = deployNew ? subnet.id : ''
output subnetName string = deployNew ? subnet.name : subnetName
