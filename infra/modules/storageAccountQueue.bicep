@description('Name of the Storage Account')
param storageAccountName string

@description('Name of the Storage Queue used for durable image-generation jobs')
param queueName string = 'image-generation-jobs'

@description('Whether to deploy the queue')
param deployNew bool = true

resource storageQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = if (deployNew) {
  name: '${storageAccountName}/default/${queueName}'
  properties: {}
}

output queueId string = deployNew ? storageQueue!.id : ''
output queueName string = queueName
