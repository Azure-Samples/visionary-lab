// File: infra/main.bicep

// This Bicep template deploys the Visionary Lab infrastructure:
// - Azure AI Foundry (AIServices) with all model deployments
// - Azure Container App Environment with backend and frontend Container Apps
// - Azure Storage Account, Cosmos DB, Container Registry, Log Analytics
// - RBAC role assignments for managed identity access (no API keys)

@description('Location for all resources')
param location string = resourceGroup().location

// Parameters for the Container App Environment and Container Apps
@description('Name of the Container App Environment')
param containerAppEnvName string = 'cae-${environmentName}'
@description('Name of the Container App')
param containerAppNameBackend string = 'ca-backend-${environmentName}'
param containerAppNameFrontend string = 'ca-frontend-${environmentName}'
param logAnalyticsWorkspaceName string = 'log-${environmentName}'

@description('Unique name for the Storage Account (3-24 lowercase letters and numbers)')
param storageAccountName string = 'st${toLower(uniqueString(resourceGroup().id, environmentName))}'

@description('Unique name for the Container Registry (5-50 lowercase letters and numbers)')
param containerRegistryName string = 'cr${toLower(uniqueString(resourceGroup().id, environmentName))}'

// AI Foundry parameters
@description('Name of the AI Foundry resource')
param aiFoundryName string
@description('Name of the AI Foundry project')
param aiProjectName string = '${aiFoundryName}-proj'
@description('Location for AI Foundry (some models are region-specific)')
param aiFoundryLocation string = 'swedencentral'

// Model deployment names
@description('Name of the LLM deployment')
param LLM_DEPLOYMENT string = 'gpt-4o'
@description('Name of the image generation deployment')
param IMAGEGEN_DEPLOYMENT string = ''
@description('Name of the gpt-image-1.5 deployment')
param IMAGEGEN_15_DEPLOYMENT string = ''
@description('Name of the gpt-image-1-mini deployment')
param IMAGEGEN_1_MINI_DEPLOYMENT string = ''
@description('Name of the Sora deployment')
param SORA_DEPLOYMENT string = ''

// Model types and versions (for Bicep-managed deployments)
param llmModelType string = 'gpt-4o'
param llmModelVersion string = '2024-11-20'
// Image/video models may be deployed via CLI when Bicep doesn't support the format
@description('Set to true to deploy image gen models via Bicep (requires OpenAI-format models)')
param deployImageGenModels bool = false
param imageGenModelType string = 'gpt-image-1'
param imageGenModelVersion string = '2024-04-01'
param imageGen15ModelVersion string = '2024-04-01'
param imageGen1MiniModelVersion string = '2024-04-01'
@description('Set to true to deploy Sora via Bicep')
param deploySoraModel bool = false
param soraModelVersion string = '2025-05-02'

// Docker images for the backend and frontend container apps
param DOCKER_IMAGE_BACKEND string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param DOCKER_IMAGE_FRONTEND string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param API_PROTOCOL string = ''
param API_HOSTNAME string = ''
param API_PORT string = ''

// Environment name for azd
param environmentName string = ''

// Parameters for Cosmos DB
param cosmosAccountName string = 'visionary-lab-cosmos'
param cosmosDatabaseName string = 'VisionaryLabDB'
param cosmosContainerName string = 'visionarylab'

// ─── Azure Storage Account ───
module storageAccountMod './modules/storageAccount.bicep' = {
  name: 'storageAccountMod'
  params: {
    location: location
    storageAccountName: storageAccountName
    deployNew: true
  }
}

module storageContainerMod './modules/storageAccountContainer.bicep' = {
  name: 'storageContainerMod'
  params: {
    storageAccountName: storageAccountName
    containerName: 'images'
    deployNew: true
  }
  dependsOn: [
    storageAccountMod
  ]
}

// ─── Azure Container Registry ───
module containerRegistryMod './modules/containerRegistry.bicep' = {
  name: 'containerRegistryMod'
  params: {
    location: location
    containerRegistryName: containerRegistryName
    deployNew: true
  }
}

// ─── Azure Cosmos DB ───
var cosmosPrefix = toLower(substring(uniqueString(resourceGroup().id, environmentName), 0, 5))
var cosmosAccountNamePrefixed = '${cosmosPrefix}-${cosmosAccountName}'
module cosmosDbMod './modules/cosmosDb.bicep' = {
  name: 'cosmosDbMod'
  params: {
    location: location
    cosmosAccountName: cosmosAccountNamePrefixed
    databaseName: cosmosDatabaseName
    containerName: cosmosContainerName
    subnetId: ''
    deployNew: true
    publicNetworkAccess: 'Enabled'
  }
}

// ─── AI Foundry (replaces separate Azure OpenAI resources) ───
module aiFoundryMod './modules/aiFoundry.bicep' = {
  name: 'aiFoundryMod'
  params: {
    aiFoundryName: aiFoundryName
    location: aiFoundryLocation
    deployNew: true
  }
}

module aiFoundryProjectMod './modules/aiFoundryProject.bicep' = {
  name: 'aiFoundryProjectMod'
  params: {
    aiProjectName: aiProjectName
    aiFoundryName: aiFoundryName
    location: aiFoundryLocation
  }
  dependsOn: [
    aiFoundryMod
  ]
}

// ─── Model Deployments (under AI Foundry) ───
// Chained sequentially — Azure doesn't support parallel deployments on the same account
module llmDeployment './modules/aiFoundryModelDeployment.bicep' = {
  name: 'llmDeployment'
  params: {
    aiFoundryName: aiFoundryName
    deploymentName: LLM_DEPLOYMENT
    modelName: llmModelType
    modelVersion: llmModelVersion
    skuCapacity: 30
  }
  dependsOn: [
    aiFoundryMod
  ]
}

module imageGenDeployment './modules/aiFoundryModelDeployment.bicep' = if (deployImageGenModels && IMAGEGEN_DEPLOYMENT != '') {
  name: 'imageGenDeployment'
  params: {
    aiFoundryName: aiFoundryName
    deploymentName: IMAGEGEN_DEPLOYMENT
    modelName: imageGenModelType
    modelVersion: imageGenModelVersion
    skuCapacity: 1
  }
  dependsOn: [
    llmDeployment
  ]
}

module imageGen15Deployment './modules/aiFoundryModelDeployment.bicep' = if (deployImageGenModels && IMAGEGEN_15_DEPLOYMENT != '') {
  name: 'imageGen15Deployment'
  params: {
    aiFoundryName: aiFoundryName
    deploymentName: IMAGEGEN_15_DEPLOYMENT
    modelName: 'gpt-image-1.5'
    modelVersion: imageGen15ModelVersion
    skuCapacity: 1
  }
  dependsOn: [
    imageGenDeployment
  ]
}

module imageGen1MiniDeployment './modules/aiFoundryModelDeployment.bicep' = if (deployImageGenModels && IMAGEGEN_1_MINI_DEPLOYMENT != '') {
  name: 'imageGen1MiniDeployment'
  params: {
    aiFoundryName: aiFoundryName
    deploymentName: IMAGEGEN_1_MINI_DEPLOYMENT
    modelName: 'gpt-image-1-mini'
    modelVersion: imageGen1MiniModelVersion
    skuCapacity: 1
  }
  dependsOn: [
    imageGen15Deployment
  ]
}

module soraDeployment './modules/aiFoundryModelDeployment.bicep' = if (deploySoraModel && SORA_DEPLOYMENT != '') {
  name: 'soraDeployment'
  params: {
    aiFoundryName: aiFoundryName
    deploymentName: SORA_DEPLOYMENT
    modelName: 'sora'
    modelVersion: soraModelVersion
    skuCapacity: 1
  }
  dependsOn: [
    imageGen1MiniDeployment
  ]
}

// ─── Container App Environment ───
module containerAppEnvMod './modules/containerAppEnv.bicep' = {
  name: 'containerAppEnvMod'
  params: {
    location: location
    containerAppEnvName: containerAppEnvName
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    subnetId: ''
    deployNew: true
  }
}

// ─── Container App: Backend ───
module containerAppBackend './modules/containerApp.bicep' = {
  name: 'containerAppBackend'
  params: {
    location: location
    containerAppName: containerAppNameBackend
    containerAppEnvId: containerAppEnvMod.outputs.containerAppEnvId
    targetPort: 80
    deployNew: true
    AZURE_BLOB_SERVICE_URL: storageAccountMod.outputs.storageAccountPrimaryEndpoint
    AZURE_STORAGE_ACCOUNT_NAME: storageAccountName
    AZURE_BLOB_IMAGE_CONTAINER: 'images'
    DOCKER_IMAGE: DOCKER_IMAGE_BACKEND
    AZURE_CONTAINER_REGISTRY_ENDPOINT: containerRegistryMod.outputs.containerRegistryLoginServer
    AZURE_CONTAINER_REGISTRY_USERNAME: containerRegistryMod.outputs.containerRegistryUsername
    AZURE_CONTAINER_REGISTRY_PASSWORD: containerRegistryMod.outputs.containerRegistryPassword
    AI_FOUNDRY_ENDPOINT: aiFoundryMod.outputs.aiFoundryEndpoint
    LLM_DEPLOYMENT: LLM_DEPLOYMENT
    IMAGEGEN_DEPLOYMENT: IMAGEGEN_DEPLOYMENT
    IMAGEGEN_15_DEPLOYMENT: IMAGEGEN_15_DEPLOYMENT
    IMAGEGEN_1_MINI_DEPLOYMENT: IMAGEGEN_1_MINI_DEPLOYMENT
    SORA_DEPLOYMENT: SORA_DEPLOYMENT
    COSMOS_ENDPOINT: cosmosDbMod.outputs.cosmosAccountEndpoint
    COSMOS_DATABASE_NAME: cosmosDbMod.outputs.databaseName
    COSMOS_CONTAINER_NAME: cosmosDbMod.outputs.containerName
    azdServiceName: 'backend'
  }
}

// ─── Container App: Frontend ───
module containerAppFrontend './modules/containerApp.bicep' = {
  name: 'containerAppFrontend'
  params: {
    location: location
    containerAppName: containerAppNameFrontend
    containerAppEnvId: containerAppEnvMod.outputs.containerAppEnvId
    targetPort: 3000
    deployNew: true
    AZURE_BLOB_SERVICE_URL: storageAccountMod.outputs.storageAccountPrimaryEndpoint
    AZURE_STORAGE_ACCOUNT_NAME: storageAccountName
    AZURE_BLOB_IMAGE_CONTAINER: 'images'
    DOCKER_IMAGE: DOCKER_IMAGE_FRONTEND
    AZURE_CONTAINER_REGISTRY_ENDPOINT: containerRegistryMod.outputs.containerRegistryLoginServer
    AZURE_CONTAINER_REGISTRY_USERNAME: containerRegistryMod.outputs.containerRegistryUsername
    AZURE_CONTAINER_REGISTRY_PASSWORD: containerRegistryMod.outputs.containerRegistryPassword
    AI_FOUNDRY_ENDPOINT: aiFoundryMod.outputs.aiFoundryEndpoint
    LLM_DEPLOYMENT: LLM_DEPLOYMENT
    IMAGEGEN_DEPLOYMENT: IMAGEGEN_DEPLOYMENT
    IMAGEGEN_15_DEPLOYMENT: IMAGEGEN_15_DEPLOYMENT
    IMAGEGEN_1_MINI_DEPLOYMENT: IMAGEGEN_1_MINI_DEPLOYMENT
    SORA_DEPLOYMENT: SORA_DEPLOYMENT
    API_PROTOCOL: API_PROTOCOL == '' ? 'https' : API_PROTOCOL
    API_PORT: API_PORT == '' ? '443' : API_PORT
    API_HOSTNAME: API_HOSTNAME == '' ? '${containerAppNameBackend}.${containerAppEnvMod.outputs.containerAppDefaultDomain}' : API_HOSTNAME
    azdServiceName: 'frontend'
  }
}

// ─── RBAC Role Assignments ───

module cosmosRoleAssignmentMod './modules/cosmosRoleAssignment.bicep' = {
  name: 'cosmosRoleAssignmentMod'
  params: {
    cosmosAccountName: cosmosAccountNamePrefixed
    containerAppPrincipalId: containerAppBackend.outputs.containerAppPrincipalId
    dataContributorRoleId: cosmosDbMod.outputs.dataContributorRoleId
  }
}

module aiFoundryRoleAssignmentMod './modules/aiFoundryRoleAssignment.bicep' = {
  name: 'aiFoundryRoleAssignmentMod'
  params: {
    aiFoundryId: aiFoundryMod.outputs.aiFoundryId
    aiFoundryName: aiFoundryName
    containerAppPrincipalId: containerAppBackend.outputs.containerAppPrincipalId
  }
}

module storageRoleAssignmentMod './modules/storageRoleAssignment.bicep' = {
  name: 'storageRoleAssignmentMod'
  params: {
    storageAccountName: storageAccountName
    containerAppPrincipalId: containerAppBackend.outputs.containerAppPrincipalId
  }
}

// ─── Outputs ───
output AZURE_LOCATION string = location
output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerAppEnvMod.outputs.containerAppEnvId
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistryMod.outputs.containerRegistryLoginServer
output BACKEND_URI string = 'https://${containerAppBackend.outputs.containerAppFqdn}'
output BACKEND_INTERNAL_URI string = 'https://${containerAppBackend.outputs.containerAppFqdn}'
output FRONTEND_URI string = 'https://${containerAppFrontend.outputs.containerAppFqdn}'
output AZURE_STORAGE_ACCOUNT_NAME string = storageAccountName
output AZURE_BLOB_SERVICE_URL string = storageAccountMod.outputs.storageAccountPrimaryEndpoint
output AI_FOUNDRY_ENDPOINT string = aiFoundryMod.outputs.aiFoundryEndpoint
output AI_FOUNDRY_NAME string = aiFoundryName
output COSMOS_DB_ENDPOINT string = cosmosDbMod.outputs.cosmosAccountEndpoint
output COSMOS_DB_DATABASE_NAME string = cosmosDbMod.outputs.databaseName
output COSMOS_DB_CONTAINER_NAME string = cosmosDbMod.outputs.containerName
