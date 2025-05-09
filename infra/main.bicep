// File: infra/main.bicep

// This Bicep template deploys an Azure Container App Environment and two Container Apps (backend and frontend) for the Visionary Lab project
// It also creates an Azure Storage Account and a Log Analytics workspace for monitoring and logging
// The backend container app is configured to use the Azure Blob Storage account and OpenAI deployments for LLM and image generation
// The frontend container app is configured to use the Azure Blob Storage account and OpenAI deployments for LLM and image generation

@description('Location for all resources')
param location string = resourceGroup().location

// Parameters for the Container App Environment and Container Apps
@description('Name of the Container App Environment')
param containerAppEnvName string = 'visionary-lab-container-env'
@description('Name of the Container App')
param containerAppNameBackend string = 'visionary-lab-backend'
param containerAppNameFrontend string = 'visionary-lab-frontend'
// Parameters for the Log Analytics workspace
param logAnalyticsWorkspaceName string = 'visionary-lab-log-analytics-workspace'

// Parameters for the Azure Storage Account
@description('Unique name for the Storage Account (3-24 lowercase letters and numbers)')
param storageAccountName string = 'a${toLower(uniqueString(resourceGroup().id, 'storage'))}'

// Parameters for the OpenAI deployments
@description('Name of the Azure OpenAI account')
param llmOpenAiAccountName string = 'myOpenAiAccount'
param llmDeploymentName string = 'gpt-4o-2'
param llmModelType string = 'gpt-4o'
param imageGenOpenAiAccountName string = 'myOpenAiAccount'
param imageGenDeploymentName string = 'gpt-image-1'
param imageGenModelType string = 'gpt-image-1'
@secure()
param IMAGEGEN_AOAI_API_KEY string
@secure()
param LLM_AOAI_API_KEY string

// Parameters for the Docker images for the backend and frontend container apps
param DOCKER_IMAGE_BACKEND string = 'aigbbemea.azurecr.io/visionarylab:latest'
param DOCKER_IMAGE_FRONTEND string = 'aigbbemea.azurecr.io/visionarylab-frontend:latest'

// Azure Storage Account
module storageAccountMod './modules/storageAccount.bicep' = {
  name: 'storageAccountMod'
  params: {
    location: location
    storageAccountName: storageAccountName
    // keyVaultName: keyVaultMod.outputs.keyVaultName
    deployNew: true  // set false to reuse an existing storage account
  }
}

// Azure Storage Account Container
// This module creates a container in the storage account for storing images
module storageContainerMod './modules/storageAccountContainer.bicep' = {
  name: 'storageContainerMod'
  params: {
    storageAccountName: storageAccountName
    containerName: 'images'
    deployNew: true  // set false to reuse an existing container
  }
  dependsOn: [
    storageAccountMod
  ]
}

// OpenAI deployment module for LLM
// This module creates an OpenAI deployment for the LLM model
module llmOpenAiAccount './modules/openAiDeployment.bicep' = {
  name: 'llmOpenAiAccount'
  params: {
    openAiAccountName: llmOpenAiAccountName
    DeploymentName: llmDeploymentName
    ModelType: llmModelType
    ModelVersion: '2024-11-20'
    location: location
    deployNew: false  // set false to reuse an existing deployment
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
    openAiAccountName: imageGenOpenAiAccountName
    DeploymentName: imageGenDeploymentName
    ModelType: imageGenModelType
    ModelVersion: '2024-11-20'
    location: location
    deployNew: false  // set false to reuse an existing deployment
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
    deployNew: true  // set false to reuse an existing environment
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
    deployNew: true  // set false to reuse an existing container app
    AZURE_BLOB_SERVICE_URL: storageAccountMod.outputs.storageAccountPrimaryEndpoint
    AZURE_STORAGE_ACCOUNT_KEY: storageAccountMod.outputs.storageAccountKey
    AZURE_STORAGE_ACCOUNT_NAME: storageAccountName
    AZURE_BLOB_IMAGE_CONTAINER: 'images'
    DOCKER_IMAGE: DOCKER_IMAGE_BACKEND
    IMAGEGEN_AOAI_API_KEY: IMAGEGEN_AOAI_API_KEY
    LLM_AOAI_API_KEY: LLM_AOAI_API_KEY
  }
  dependsOn: [
    storageAccountMod
    storageContainerMod
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
    deployNew: true  // set false to reuse an existing container app
    AZURE_BLOB_SERVICE_URL: storageAccountMod.outputs.storageAccountPrimaryEndpoint
    AZURE_STORAGE_ACCOUNT_KEY: storageAccountMod.outputs.storageAccountKey
    AZURE_STORAGE_ACCOUNT_NAME: storageAccountName
    AZURE_BLOB_IMAGE_CONTAINER: 'images'
    DOCKER_IMAGE: DOCKER_IMAGE_FRONTEND
    IMAGEGEN_AOAI_API_KEY: IMAGEGEN_AOAI_API_KEY
    LLM_AOAI_API_KEY: LLM_AOAI_API_KEY
  }
  dependsOn: [
    storageAccountMod
    storageContainerMod
  ]
}
