param openAiAccountName string 
param location string = resourceGroup().location
param skuName string = 'S0'
param DeploymentName string
param ModelType string = 'gpt-4o'
param ModelVersion string = '2024-11-20'
param Capacity int = 30 // The number of capacity units for the deployment
param deployNew bool = true // Set to false to reuse an existing OpenAI account

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2022-12-01' = if (deployNew) {
  name: openAiAccountName
  location: location
  kind: 'OpenAI'
  sku: {
    name: skuName
  }
  properties: {
  }
}

// If the OpenAI account already exists, we need to reference it by its resource ID
// and not create a new one. This is important for deployments that are not new.
// The resource ID is used to reference the existing OpenAI account.

resource existingOpenAiAccount 'Microsoft.CognitiveServices/accounts@2022-12-01' existing = if (!deployNew) {
  name: openAiAccountName
  scope: resourceGroup()
}

resource openAiDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployNew) {
  // Create a new deployment for the OpenAI account
  name: DeploymentName
  parent: openAiAccount
  sku: {
    name: 'GlobalStandard'
    capacity: Capacity
  }
  properties: {
    model: {
      name: ModelType
      format: 'OpenAI'
      version: ModelVersion
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}
output openAiResourceId string = deployNew ? openAiAccount.id : existingOpenAiAccount.id
