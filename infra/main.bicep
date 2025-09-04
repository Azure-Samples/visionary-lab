// File: infra/main.bicep

// This Bicep template deploys an Azure Container App Environment and two Container Apps (backend and frontend) for the Visionary Lab project
// It also creates an Azure Storage Account and a Log Analytics workspace for monitoring and logging
// The backend container app is configured to use the Azure Blob Storage account and OpenAI deployments for LLM and image generation
// The frontend container app is configured to use the Azure Blob Storage account and OpenAI deployments for LLM and image generation

@description('Location for all resources')
param location string = resourceGroup().location

// Parameters for the Container App Environment and Container Apps
@description('Name of the Container App Environment')
param containerAppEnvName string = 'cae-${environmentName}'
@description('Name of the Container App')
param containerAppNameBackend string = 'ca-backend-${environmentName}'
param containerAppNameFrontend string = 'ca-frontend-${environmentName}'
// Parameters for the Log Analytics workspace
param logAnalyticsWorkspaceName string = 'log-${environmentName}'

// Parameters for the Azure Storage Account
@description('Unique name for the Storage Account (3-24 lowercase letters and numbers)')
param storageAccountName string = 'st${toLower(uniqueString(resourceGroup().id, environmentName))}'

// Parameters for the Azure Container Registry
@description('Unique name for the Container Registry (5-50 lowercase letters and numbers)')
param containerRegistryName string = 'cr${toLower(uniqueString(resourceGroup().id, environmentName))}'

// Parameters for the OpenAI deployments - LLM
@description('Name of the Azure OpenAI resource for LLM')
param LLM_AOAI_RESOURCE string
@description('Name of the LLM deployment')
param LLM_DEPLOYMENT string
@secure()
@description('API key for LLM Azure OpenAI service')
param LLM_AOAI_API_KEY string

// Parameters for the OpenAI deployments - Image Generation
@description('Name of the Azure OpenAI resource for image generation')
param IMAGEGEN_AOAI_RESOURCE string
@description('Name of the image generation deployment')
param IMAGEGEN_DEPLOYMENT string
@secure()
@description('API key for image generation Azure OpenAI service')
param IMAGEGEN_AOAI_API_KEY string

// Parameters for the OpenAI deployments - Sora
@description('Name of the Azure OpenAI resource for Sora')
param SORA_AOAI_RESOURCE string
@description('Name of the Sora deployment')
param SORA_DEPLOYMENT string
@secure()
@description('API key for Sora Azure OpenAI service')
param SORA_AOAI_API_KEY string

// Model types (internal use)
param llmModelType string = 'gpt-4o'
param imageGenModelType string = 'gpt-image-1'
// Parameters for the Docker images for the backend and frontend container apps
param DOCKER_IMAGE_BACKEND string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param DOCKER_IMAGE_FRONTEND string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param API_PROTOCOL string = ''
param API_HOSTNAME string = ''
param API_PORT string = ''

// Environment name for azd
param environmentName string = ''
param principalId string = ''

// Parameters for Cosmos DB
param cosmosAccountName string = 'visionary-lab-cosmos'
param cosmosDatabaseName string = 'VisionaryLabDB'
param cosmosContainerName string = 'visionarylab'

// Azure Storage Account
module storageAccountMod './modules/storageAccount.bicep' = {
  name: 'storageAccountMod'
  params: {
    location: location
    storageAccountName: storageAccountName
    // keyVaultName: keyVaultMod.outputs.keyVaultName
    deployNew: true // set false to reuse an existing storage account
  }
}


// Azure Storage Account Container
// This module creates a container in the storage account for storing images
module storageContainerMod './modules/storageAccountContainer.bicep' = {
  name: 'storageContainerMod'
  params: {
    storageAccountName: storageAccountName
    containerName: 'images'
    deployNew: true // set false to reuse an existing container
  }
  dependsOn: [
    storageAccountMod
  ]
}

// Azure Container Registry
// This module creates a container registry for storing Docker images
module containerRegistryMod './modules/containerRegistry.bicep' = {
  name: 'containerRegistryMod'
  params: {
    location: location
    containerRegistryName: containerRegistryName
    deployNew: true  // set false to reuse an existing container registry
  }
}

// Add this module after your storage modules
// Azure Cosmos DB Account for Visionary Lab
// This module creates a Cosmos DB account with SQL API for storing Visionary Lab data
module cosmosDbMod './modules/cosmosDb.bicep' = {
  name: 'cosmosDbMod'
  params: {
    location: location
    cosmosAccountName: cosmosAccountName
    databaseName: cosmosDatabaseName
    containerName: cosmosContainerName
    deployNew: true // set false to reuse an existing Cosmos DB account
  }
}

// OpenAI deployment module for LLM
// This module creates an OpenAI deployment for the LLM model
module llmOpenAiAccount './modules/openAiDeployment.bicep' = {
  name: 'llmOpenAiAccount'
  params: {
    openAiAccountName: LLM_AOAI_RESOURCE
    DeploymentName: LLM_DEPLOYMENT
    ModelType: llmModelType
    ModelVersion: '2024-11-20'
    location: location
    deployNew: false // set false to reuse an existing deployment
  }
  dependsOn: [
    // keyVaultMod
    storageAccountMod
  ]
}

// OpenAI deployment for Image Generation
// This module creates an OpenAI deployment for the image generation models
module imageGenOpenAiAccount './modules/openAiDeployment.bicep' = {
  name: 'imageGenOpenAiAccount'
  params: {
    openAiAccountName: IMAGEGEN_AOAI_RESOURCE
    DeploymentName: IMAGEGEN_DEPLOYMENT
    ModelType: imageGenModelType
    ModelVersion: '2024-11-20'
    location: location
    deployNew: false // set false to reuse an existing deployment
  }
  dependsOn: [
    storageAccountMod
  ]
}

// Azure Container App Environment
// This module creates a container app environment for the backend and frontend container apps
// It also creates a Log Analytics workspace for monitoring and logging
// The Log Analytics workspace is linked to the container app environment
module containerAppEnvMod './modules/containerAppEnv.bicep' = {
  name: 'containerAppEnvMod'
  params: {
    location: location
    containerAppEnvName: containerAppEnvName
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    deployNew: true // set false to reuse an existing environment
  }
}

// Container App for Backend
// This module creates a container app for the backend service
// It uses the container app environment created in the previous module
// The container app is configured to use the Azure Blob Storage account and OpenAI deployments for LLM and image generation
module containerAppBackend './modules/containerApp.bicep' = {
  name: 'containerAppBackend'
  params: {
    location: location
    containerAppName: containerAppNameBackend
    containerAppEnvId: containerAppEnvMod.outputs.containerAppEnvId
    targetPort: 80
    deployNew: true // set false to reuse an existing container app
    AZURE_BLOB_SERVICE_URL: storageAccountMod.outputs.storageAccountPrimaryEndpoint
    AZURE_STORAGE_ACCOUNT_KEY: storageAccountMod.outputs.storageAccountKey
    AZURE_STORAGE_ACCOUNT_NAME: storageAccountName
    AZURE_BLOB_IMAGE_CONTAINER: 'images'
    DOCKER_IMAGE: DOCKER_IMAGE_BACKEND
    AZURE_CONTAINER_REGISTRY_ENDPOINT: containerRegistryMod.outputs.containerRegistryLoginServer
    AZURE_CONTAINER_REGISTRY_USERNAME: containerRegistryMod.outputs.containerRegistryUsername
    AZURE_CONTAINER_REGISTRY_PASSWORD: containerRegistryMod.outputs.containerRegistryPassword
    IMAGEGEN_AOAI_RESOURCE: IMAGEGEN_AOAI_RESOURCE
    IMAGEGEN_DEPLOYMENT: IMAGEGEN_DEPLOYMENT
    IMAGEGEN_AOAI_API_KEY: IMAGEGEN_AOAI_API_KEY
    LLM_AOAI_RESOURCE: LLM_AOAI_RESOURCE
    LLM_DEPLOYMENT: LLM_DEPLOYMENT
    LLM_AOAI_API_KEY: LLM_AOAI_API_KEY
    SORA_AOAI_RESOURCE: SORA_AOAI_RESOURCE
    SORA_DEPLOYMENT: SORA_DEPLOYMENT
    SORA_AOAI_API_KEY: SORA_AOAI_API_KEY
    COSMOS_ENDPOINT: cosmosDbMod.outputs.cosmosAccountEndpoint
    COSMOS_DATABASE_NAME: cosmosDbMod.outputs.databaseName
    COSMOS_CONTAINER_NAME: cosmosDbMod.outputs.containerName
    COSMOS_DB_KEY: cosmosDbMod.outputs.primaryKey
    azdServiceName: 'backend'
  }
  dependsOn: [
    storageAccountMod
    storageContainerMod
    containerRegistryMod
    cosmosDbMod
  ]
}

// Container App for Frontend
// This module creates a container app for the frontend service
// It uses the container app environment created in the previous module
// The container app is configured to use the Azure Blob Storage account and OpenAI deployments for LLM and image generation
module containerAppFrontend './modules/containerApp.bicep' = {
  name: 'containerAppFrontend'
  params: {
    location: location
    containerAppName: containerAppNameFrontend
    containerAppEnvId: containerAppEnvMod.outputs.containerAppEnvId
    targetPort: 3000
    deployNew: true // set false to reuse an existing container app
    AZURE_BLOB_SERVICE_URL: storageAccountMod.outputs.storageAccountPrimaryEndpoint
    AZURE_STORAGE_ACCOUNT_KEY: storageAccountMod.outputs.storageAccountKey
    AZURE_STORAGE_ACCOUNT_NAME: storageAccountName
    AZURE_BLOB_IMAGE_CONTAINER: 'images'
    DOCKER_IMAGE: DOCKER_IMAGE_FRONTEND
    AZURE_CONTAINER_REGISTRY_ENDPOINT: containerRegistryMod.outputs.containerRegistryLoginServer
    AZURE_CONTAINER_REGISTRY_USERNAME: containerRegistryMod.outputs.containerRegistryUsername
    AZURE_CONTAINER_REGISTRY_PASSWORD: containerRegistryMod.outputs.containerRegistryPassword
    IMAGEGEN_AOAI_RESOURCE: IMAGEGEN_AOAI_RESOURCE
    IMAGEGEN_DEPLOYMENT: IMAGEGEN_DEPLOYMENT
    IMAGEGEN_AOAI_API_KEY: IMAGEGEN_AOAI_API_KEY
    LLM_AOAI_RESOURCE: LLM_AOAI_RESOURCE
    LLM_DEPLOYMENT: LLM_DEPLOYMENT
    LLM_AOAI_API_KEY: LLM_AOAI_API_KEY
    API_PROTOCOL: API_PROTOCOL == '' ? 'https' : API_PROTOCOL
    API_PORT: API_PORT == '' ? '443' : API_PORT
    API_HOSTNAME: API_HOSTNAME == '' ? '${containerAppNameBackend}.${containerAppEnvMod.outputs.containerAppDefaultDomain}' : API_HOSTNAME
    azdServiceName: 'frontend'
  }
  dependsOn: [
    storageAccountMod
    storageContainerMod
    containerRegistryMod
  ]
}

// Outputs for azd
output AZURE_LOCATION string = location
output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerAppEnvMod.outputs.containerAppEnvId
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistryMod.outputs.containerRegistryLoginServer
output BACKEND_URI string = 'https://${containerAppBackend.outputs.containerAppFqdn}'
output FRONTEND_URI string = 'https://${containerAppFrontend.outputs.containerAppFqdn}'
output AZURE_STORAGE_ACCOUNT_NAME string = storageAccountName
output AZURE_BLOB_SERVICE_URL string = storageAccountMod.outputs.storageAccountPrimaryEndpoint

// Cosmos DB outputs
output COSMOS_DB_ENDPOINT string = cosmosDbMod.outputs.cosmosAccountEndpoint
output COSMOS_DB_DATABASE_NAME string = cosmosDbMod.outputs.databaseName
output COSMOS_DB_CONTAINER_NAME string = cosmosDbMod.outputs.containerName
output COSMOS_DB_PRIMARY_KEY string = cosmosDbMod.outputs.primaryKey
