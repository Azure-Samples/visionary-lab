param location string
param storageAccountName string = 'a${toLower(uniqueString(resourceGroup().id, 'storage'))}'
// param keyVaultName string
param deployNew bool = true

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' = if(deployNew) {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    publicNetworkAccess: 'Disabled'
    allowBlobPublicAccess: false
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'None'
    }
  }
}

output storageAccountPrimaryEndpoint string = deployNew ? storageAccount!.properties.primaryEndpoints.blob : ''
output storageAccountQueueEndpoint string = deployNew ? storageAccount!.properties.primaryEndpoints.queue : ''
output storageAccountId string = deployNew ? storageAccount!.id : ''
output storageAccountName string = storageAccountName
