param location string
param storageAccountName string
// param keyVaultName string
param deployNew bool = true

resource storageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' = if(deployNew) {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {}
}

output storageAccountPrimaryEndpoint string = storageAccount.properties.primaryEndpoints.blob
output storageAccountId string = storageAccount.id
@secure()
output storageAccountKey string = storageAccount.listKeys().keys[0].value

