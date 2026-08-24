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
@description('Name of the image-generation worker Container App')
param containerAppNameImageWorker string = 'ca-image-worker-${environmentName}'
param containerAppNameFrontend string = 'ca-frontend-${environmentName}'
param logAnalyticsWorkspaceName string = 'log-${environmentName}'

@description('Unique name for the Storage Account (3-24 lowercase letters and numbers)')
param storageAccountName string = 'st${toLower(uniqueString(resourceGroup().id, environmentName))}'

@description('Name of the Storage Queue used for durable image-generation jobs')
param imageGenerationQueueName string = 'image-generation-jobs'

@description('Name of the poison queue used after terminal worker failures')
param imageGenerationPoisonQueueName string = 'image-generation-jobs-poison'

@description('Optional explicit browser origins for Blob CORS; defaults to the deployed frontend origins')
param storageBlobCorsAllowedOrigins array = []

@minValue(1)
@description('Maximum number of image-worker replicas processing generation jobs')
param imageWorkerMaxReplicas int = 10

@minValue(1)
@description('Concurrent image-generation jobs processed by each worker replica')
param imageWorkerConcurrency int = 2

@minValue(1)
@description('Queued image-generation messages per worker replica')
param imageGenerationQueueScaleTargetLength int = 2

@description('Unique name for the Container Registry (5-50 lowercase letters and numbers)')
param containerRegistryName string = 'cr${toLower(uniqueString(resourceGroup().id, environmentName))}'

@description('User-assigned identity name used by the worker to pull from ACR')
param imageWorkerRegistryIdentityName string = 'id-image-worker-acr-${environmentName}'

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
@description('Name of the FLUX Kontext Pro deployment')
param FLUX_KONTEXT_DEPLOYMENT string = ''

// Model types and versions (for Bicep-managed deployments)
param llmModelType string = 'gpt-4o'
param llmModelVersion string = '2024-11-20'
// Image/video models may be deployed via CLI when Bicep doesn't support the format
@description('Set to true to deploy image gen models via Bicep (requires OpenAI-format models)')
param deployImageGenModels bool = false
param imageGenModelType string = 'gpt-image-1.5'
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

// Easy Auth for frontend (Microsoft tenant restriction)
@secure()
param AUTH_CLIENT_ID string = ''
@secure()
param AUTH_CLIENT_SECRET string = ''
param AUTH_ISSUER string = ''

// Environment name for azd
param environmentName string = ''

// VNet parameters
@description('Name of the Virtual Network')
param vnetName string = 'vnet-${environmentName}'

// Front Door parameters
@description('Name of the Azure Front Door profile')
param frontDoorName string = 'afd-${environmentName}'

// Custom domain for frontend
@description('Custom domain name for the frontend (e.g., visionary.go-agentic.com). Leave empty to skip.')
param frontendCustomDomain string = ''
@description('Managed certificate resource ID for the custom domain. Leave empty for first-time setup.')
param frontendCertificateId string = ''

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

module storageQueueMod './modules/storageAccountQueue.bicep' = {
  name: 'storageQueueMod'
  params: {
    storageAccountName: storageAccountName
    queueName: imageGenerationQueueName
    deployNew: true
  }
  dependsOn: [
    storageAccountMod
  ]
}

module storagePoisonQueueMod './modules/storageAccountQueue.bicep' = {
  name: 'storagePoisonQueueMod'
  params: {
    storageAccountName: storageAccountName
    queueName: imageGenerationPoisonQueueName
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

// A user-assigned pull identity avoids the create-time chicken-and-egg problem
// of authenticating a brand-new Container App to ACR with its system identity.
resource imageWorkerRegistryIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: imageWorkerRegistryIdentityName
  location: location
}

module containerRegistryWorkerRoleAssignmentMod './modules/containerRegistryRoleAssignment.bicep' = {
  name: 'containerRegistryWorkerRoleAssignmentMod'
  params: {
    containerRegistryName: containerRegistryName
    principalId: imageWorkerRegistryIdentity.properties.principalId
  }
  dependsOn: [
    containerRegistryMod
  ]
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
    publicNetworkAccess: 'Disabled'
  }
}

// ─── Virtual Network ───
module vnetMod './modules/virtualNetwork.bicep' = {
  name: 'vnetMod'
  params: {
    location: location
    vnetName: vnetName
  }
}

// ─── Private DNS Zones ───
module blobDnsZoneMod './modules/privateDnsZone.bicep' = {
  name: 'blobDnsZoneMod'
  params: {
    zoneName: 'privatelink.blob.${environment().suffixes.storage}'
    vnetId: vnetMod.outputs.vnetId
  }
}

module queueDnsZoneMod './modules/privateDnsZone.bicep' = {
  name: 'queueDnsZoneMod'
  params: {
    zoneName: 'privatelink.queue.${environment().suffixes.storage}'
    vnetId: vnetMod.outputs.vnetId
  }
}

module cosmosDnsZoneMod './modules/privateDnsZone.bicep' = {
  name: 'cosmosDnsZoneMod'
  params: {
    zoneName: 'privatelink.documents.azure.com'
    vnetId: vnetMod.outputs.vnetId
  }
}

// ─── Private Endpoints ───
module storagePrivateEndpointMod './modules/privateEndpoint.bicep' = {
  name: 'storagePrivateEndpointMod'
  params: {
    location: location
    privateEndpointName: 'pe-storage-${environmentName}'
    subnetId: vnetMod.outputs.privateEndpointsSubnetId
    privateLinkServiceId: storageAccountMod.outputs.storageAccountId
    groupIds: ['blob']
    privateDnsZoneId: blobDnsZoneMod.outputs.privateDnsZoneId
  }
}

module storageQueuePrivateEndpointMod './modules/privateEndpoint.bicep' = {
  name: 'storageQueuePrivateEndpointMod'
  params: {
    location: location
    privateEndpointName: 'pe-storage-queue-${environmentName}'
    subnetId: vnetMod.outputs.privateEndpointsSubnetId
    privateLinkServiceId: storageAccountMod.outputs.storageAccountId
    groupIds: ['queue']
    privateDnsZoneId: queueDnsZoneMod.outputs.privateDnsZoneId
  }
}

module cosmosPrivateEndpointMod './modules/privateEndpoint.bicep' = {
  name: 'cosmosPrivateEndpointMod'
  params: {
    location: location
    privateEndpointName: 'pe-cosmos-${environmentName}'
    subnetId: vnetMod.outputs.privateEndpointsSubnetId
    privateLinkServiceId: cosmosDbMod.outputs.cosmosAccountId
    groupIds: ['Sql']
    privateDnsZoneId: cosmosDnsZoneMod.outputs.privateDnsZoneId
  }
}

// ─── Azure Front Door (CDN with private link to storage) ───
var storageHostName = replace(replace(storageAccountMod.outputs.storageAccountPrimaryEndpoint, 'https://', ''), '/', '')
module frontDoorMod './modules/frontDoor.bicep' = {
  name: 'frontDoorMod'
  params: {
    frontDoorName: frontDoorName
    storageAccountHostName: storageHostName
    storageAccountId: storageAccountMod.outputs.storageAccountId
    storageAccountLocation: location
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
    subnetId: vnetMod.outputs.containerAppsSubnetId
    deployNew: true
  }
}

var deployedFrontendOrigins = concat(
  [
    'https://${containerAppNameFrontend}.${containerAppEnvMod.outputs.containerAppDefaultDomain}'
  ],
  frontendCustomDomain != '' ? [
    'https://${frontendCustomDomain}'
  ] : []
)
var effectiveBlobCorsAllowedOrigins = length(storageBlobCorsAllowedOrigins) > 0
  ? storageBlobCorsAllowedOrigins
  : deployedFrontendOrigins

module storageBlobServiceMod './modules/storageBlobService.bicep' = {
  name: 'storageBlobServiceMod'
  params: {
    storageAccountName: storageAccountName
    allowedOrigins: effectiveBlobCorsAllowedOrigins
  }
  dependsOn: [
    storageAccountMod
  ]
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
    enableIngress: true
    externalIngress: false
    AZURE_BLOB_SERVICE_URL: storageAccountMod.outputs.storageAccountPrimaryEndpoint
    AZURE_STORAGE_ACCOUNT_NAME: storageAccountName
    AZURE_BLOB_IMAGE_CONTAINER: 'images'
    AZURE_STORAGE_QUEUE_URL: storageAccountMod.outputs.storageAccountQueueEndpoint
    AZURE_STORAGE_QUEUE_NAME: imageGenerationQueueName
    AZURE_STORAGE_POISON_QUEUE_NAME: imageGenerationPoisonQueueName
    CORS_ALLOWED_ORIGINS: join(effectiveBlobCorsAllowedOrigins, ',')
    IMAGE_JOB_ROLE: 'api'
    IMAGE_JOB_MODE: 'azure'
    enableQueueScaleRule: false
    CDN_BLOB_URL: 'https://${frontDoorMod.outputs.frontDoorEndpointHostName}'
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
    FLUX_KONTEXT_DEPLOYMENT: FLUX_KONTEXT_DEPLOYMENT
    COSMOS_ENDPOINT: cosmosDbMod.outputs.cosmosAccountEndpoint
    COSMOS_DATABASE_NAME: cosmosDbMod.outputs.databaseName
    COSMOS_CONTAINER_NAME: cosmosDbMod.outputs.containerName
    azdServiceName: 'backend'
  }
  dependsOn: [
    storageBlobServiceMod
    storageQueueMod
    storagePoisonQueueMod
    storageQueuePrivateEndpointMod
  ]
}

// ─── Container App: Image-generation worker ───
// The worker uses the backend image but has no HTTP surface. KEDA starts replicas
// only when durable queue messages are available.
module containerAppImageWorker './modules/containerApp.bicep' = {
  name: 'containerAppImageWorker'
  params: {
    location: location
    containerAppName: containerAppNameImageWorker
    containerAppEnvId: containerAppEnvMod.outputs.containerAppEnvId
    deployNew: true
    enableIngress: false
    enableHttpProbe: false
    containerCpu: 2
    containerMemory: '4Gi'
    minReplicas: 0
    maxReplicas: imageWorkerMaxReplicas
    enableQueueScaleRule: true
    queueScaleTargetLength: imageGenerationQueueScaleTargetLength
    IMAGE_JOB_ROLE: 'worker'
    IMAGE_JOB_MODE: 'azure'
    IMAGE_JOB_CONCURRENCY: imageWorkerConcurrency
    AZURE_BLOB_SERVICE_URL: storageAccountMod.outputs.storageAccountPrimaryEndpoint
    AZURE_STORAGE_ACCOUNT_NAME: storageAccountName
    AZURE_BLOB_IMAGE_CONTAINER: 'images'
    AZURE_STORAGE_QUEUE_URL: storageAccountMod.outputs.storageAccountQueueEndpoint
    AZURE_STORAGE_QUEUE_NAME: imageGenerationQueueName
    AZURE_STORAGE_POISON_QUEUE_NAME: imageGenerationPoisonQueueName
    CORS_ALLOWED_ORIGINS: join(effectiveBlobCorsAllowedOrigins, ',')
    CDN_BLOB_URL: 'https://${frontDoorMod.outputs.frontDoorEndpointHostName}'
    DOCKER_IMAGE: DOCKER_IMAGE_BACKEND
    AZURE_CONTAINER_REGISTRY_ENDPOINT: containerRegistryMod.outputs.containerRegistryLoginServer
    registryIdentityResourceId: imageWorkerRegistryIdentity.id
    AI_FOUNDRY_ENDPOINT: aiFoundryMod.outputs.aiFoundryEndpoint
    LLM_DEPLOYMENT: LLM_DEPLOYMENT
    IMAGEGEN_DEPLOYMENT: IMAGEGEN_DEPLOYMENT
    IMAGEGEN_15_DEPLOYMENT: IMAGEGEN_15_DEPLOYMENT
    IMAGEGEN_1_MINI_DEPLOYMENT: IMAGEGEN_1_MINI_DEPLOYMENT
    SORA_DEPLOYMENT: SORA_DEPLOYMENT
    FLUX_KONTEXT_DEPLOYMENT: FLUX_KONTEXT_DEPLOYMENT
    COSMOS_ENDPOINT: cosmosDbMod.outputs.cosmosAccountEndpoint
    COSMOS_DATABASE_NAME: cosmosDbMod.outputs.databaseName
    COSMOS_CONTAINER_NAME: cosmosDbMod.outputs.containerName
  }
  dependsOn: [
    containerRegistryWorkerRoleAssignmentMod
    storageBlobServiceMod
    storageQueueMod
    storagePoisonQueueMod
    storageQueuePrivateEndpointMod
  ]
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
    CDN_BLOB_URL: 'https://${frontDoorMod.outputs.frontDoorEndpointHostName}'
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
    FLUX_KONTEXT_DEPLOYMENT: FLUX_KONTEXT_DEPLOYMENT
    API_PROTOCOL: API_PROTOCOL == '' ? 'https' : API_PROTOCOL
    API_PORT: API_PORT == '' ? '443' : API_PORT
    API_HOSTNAME: API_HOSTNAME == '' ? '${containerAppNameBackend}.${containerAppEnvMod.outputs.containerAppDefaultDomain}' : API_HOSTNAME
    enableAuth: AUTH_CLIENT_ID != ''
    authClientId: AUTH_CLIENT_ID
    authClientSecret: AUTH_CLIENT_SECRET
    authIssuer: AUTH_ISSUER
    customDomainName: frontendCustomDomain
    certificateId: frontendCertificateId
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

module cosmosWorkerRoleAssignmentMod './modules/cosmosRoleAssignment.bicep' = {
  name: 'cosmosWorkerRoleAssignmentMod'
  params: {
    cosmosAccountName: cosmosAccountNamePrefixed
    containerAppPrincipalId: containerAppImageWorker.outputs.containerAppPrincipalId
    dataContributorRoleId: cosmosDbMod.outputs.dataContributorRoleId
  }
}

module aiFoundryWorkerRoleAssignmentMod './modules/aiFoundryRoleAssignment.bicep' = {
  name: 'aiFoundryWorkerRoleAssignmentMod'
  params: {
    aiFoundryId: aiFoundryMod.outputs.aiFoundryId
    aiFoundryName: aiFoundryName
    containerAppPrincipalId: containerAppImageWorker.outputs.containerAppPrincipalId
  }
}

module storageWorkerRoleAssignmentMod './modules/storageRoleAssignment.bicep' = {
  name: 'storageWorkerRoleAssignmentMod'
  params: {
    storageAccountName: storageAccountName
    containerAppPrincipalId: containerAppImageWorker.outputs.containerAppPrincipalId
  }
}

// ─── Outputs ───
output AZURE_LOCATION string = location
output AZURE_CONTAINER_ENVIRONMENT_NAME string = containerAppEnvMod.outputs.containerAppEnvId
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistryMod.outputs.containerRegistryLoginServer
output BACKEND_CONTAINER_APP_NAME string = containerAppNameBackend
output BACKEND_URI string = frontendCustomDomain != ''
  ? 'https://${frontendCustomDomain}/api/backend'
  : 'https://${containerAppFrontend.outputs.containerAppFqdn}/api/backend'
output BACKEND_INTERNAL_URI string = 'https://${containerAppBackend.outputs.containerAppFqdn}'
output IMAGE_WORKER_CONTAINER_APP_NAME string = containerAppNameImageWorker
output FRONTEND_URI string = 'https://${containerAppFrontend.outputs.containerAppFqdn}'
output AZURE_STORAGE_ACCOUNT_NAME string = storageAccountName
output AZURE_BLOB_SERVICE_URL string = storageAccountMod.outputs.storageAccountPrimaryEndpoint
output AZURE_STORAGE_QUEUE_URL string = storageAccountMod.outputs.storageAccountQueueEndpoint
output AZURE_STORAGE_QUEUE_NAME string = imageGenerationQueueName
output AZURE_STORAGE_POISON_QUEUE_NAME string = imageGenerationPoisonQueueName
output AI_FOUNDRY_ENDPOINT string = aiFoundryMod.outputs.aiFoundryEndpoint
output AI_FOUNDRY_NAME string = aiFoundryName
output COSMOS_DB_ENDPOINT string = cosmosDbMod.outputs.cosmosAccountEndpoint
output COSMOS_DB_DATABASE_NAME string = cosmosDbMod.outputs.databaseName
output COSMOS_DB_CONTAINER_NAME string = cosmosDbMod.outputs.containerName
output CDN_BLOB_URL string = 'https://${frontDoorMod.outputs.frontDoorEndpointHostName}'
