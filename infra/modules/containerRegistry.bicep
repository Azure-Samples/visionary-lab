param location string
param containerRegistryName string
param deployNew bool = true

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = if(deployNew) {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Reference existing registry when not deploying new
resource existingRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = if(!deployNew) {
  name: containerRegistryName
}

output containerRegistryId string = deployNew ? containerRegistry.id : existingRegistry.id
output containerRegistryName string = deployNew ? containerRegistry.name : existingRegistry.name
output containerRegistryLoginServer string = deployNew ? containerRegistry.properties.loginServer : existingRegistry.properties.loginServer
output containerRegistryUsername string = deployNew ? containerRegistry.listCredentials().username : existingRegistry.listCredentials().username
output containerRegistryPassword string = deployNew ? containerRegistry.listCredentials().passwords[0].value : existingRegistry.listCredentials().passwords[0].value