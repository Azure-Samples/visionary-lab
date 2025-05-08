param storageAccountName string
param containerName string
param deployNew bool = true

resource storageContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = if (deployNew) {
  name: '${storageAccountName}/default/${containerName}'
  properties: {
    publicAccess: 'None'
  }
}

output containerId string = storageContainer.id
