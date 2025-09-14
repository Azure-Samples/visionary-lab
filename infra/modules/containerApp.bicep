param location string
param containerAppName string
param containerAppEnvId string
param DOCKER_IMAGE string
param deployNew bool = true
param azdServiceName string = ''

// Env Variables
param MODEL_PROVIDER string = 'azure'
// Azure OpenAI Image Generation
param IMAGEGEN_AOAI_RESOURCE string = 'aoai-akc-uswest3'
param IMAGEGEN_DEPLOYMENT string = 'gpt-image-1'
@secure()
param IMAGEGEN_AOAI_API_KEY string
// Azure OpenAI LLM
param LLM_AOAI_RESOURCE string = 'emea-gbb-sweden-central'
param LLM_DEPLOYMENT string = 'gpt-4o-2'
@secure()
param LLM_AOAI_API_KEY string
// Azure OpenAI Sora
param SORA_AOAI_RESOURCE string = 'aoai-akc-uswest3'
param SORA_DEPLOYMENT string = 'sora'
@secure()
param SORA_AOAI_API_KEY string = ''
// Azure Blob Storage
param AZURE_BLOB_SERVICE_URL string
param AZURE_STORAGE_ACCOUNT_NAME string
param AZURE_STORAGE_ACCOUNT_KEY string
param AZURE_BLOB_IMAGE_CONTAINER string = 'images'

param targetPort int = 80
param API_PROTOCOL string = 'http'
param API_HOSTNAME string = 'localhost'
param API_PORT string = '80'
// Add these parameters to your containerApp.bicep file
param COSMOS_ENDPOINT string = ''
param COSMOS_DATABASE_NAME string = ''
param COSMOS_CONTAINER_NAME string = ''
// @secure()
// param COSMOS_DB_KEY string = '' // Removed for managed identity

// Azure Container Registry parameters
param AZURE_CONTAINER_REGISTRY_ENDPOINT string = ''
@secure()
param AZURE_CONTAINER_REGISTRY_USERNAME string = ''
@secure()
param AZURE_CONTAINER_REGISTRY_PASSWORD string = ''

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = if(deployNew) {
  name: containerAppName
  location: location
  tags: azdServiceName != '' ? {
    'azd-service-name': azdServiceName
  } : {}
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppEnvId
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'Auto'
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
      }
      registries: AZURE_CONTAINER_REGISTRY_ENDPOINT != '' ? [
        {
          server: AZURE_CONTAINER_REGISTRY_ENDPOINT
          username: AZURE_CONTAINER_REGISTRY_USERNAME
          passwordSecretRef: 'acr-password'
        }
      ] : []
      secrets: AZURE_CONTAINER_REGISTRY_ENDPOINT != '' ? [
        {
          name: 'acr-password'
          value: AZURE_CONTAINER_REGISTRY_PASSWORD
        }
      ] : []
    }
    template: {
      containers: [
        {
          name: containerAppName
          image: DOCKER_IMAGE
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: '/'
                port: targetPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
          ]
          env: [
            {
              name: 'MODEL_PROVIDER'
              value: MODEL_PROVIDER
            }
            {
              name: 'IMAGEGEN_AOAI_RESOURCE'
              value: IMAGEGEN_AOAI_RESOURCE
            }
            {
              name: 'IMAGEGEN_DEPLOYMENT'
              value: IMAGEGEN_DEPLOYMENT
            }
            {
              name: 'IMAGEGEN_AOAI_API_KEY'
              value: IMAGEGEN_AOAI_API_KEY
            }
            {
              name: 'LLM_AOAI_RESOURCE'
              value: LLM_AOAI_RESOURCE
            }
            {
              name: 'LLM_DEPLOYMENT'
              value: LLM_DEPLOYMENT
            }
            {
              name: 'LLM_AOAI_API_KEY'
              value: LLM_AOAI_API_KEY
            }
            {
              name: 'SORA_AOAI_RESOURCE'
              value: SORA_AOAI_RESOURCE
            }
            {
              name: 'SORA_DEPLOYMENT'
              value: SORA_DEPLOYMENT
            }
            {
              name: 'SORA_AOAI_API_KEY'
              value: SORA_AOAI_API_KEY
            }
            {
              name: 'AZURE_BLOB_SERVICE_URL'
              value: AZURE_BLOB_SERVICE_URL
            }
            {
              name: 'AZURE_STORAGE_ACCOUNT_NAME'
              value: AZURE_STORAGE_ACCOUNT_NAME
            }
            {
              name: 'AZURE_STORAGE_ACCOUNT_KEY'
              value: AZURE_STORAGE_ACCOUNT_KEY
            }
            {
              name: 'AZURE_BLOB_IMAGE_CONTAINER'
              value: AZURE_BLOB_IMAGE_CONTAINER
            }
            {
              name: 'API_PROTOCOL'
              value: API_PROTOCOL
            }
            {
              name: 'API_HOSTNAME'
              value: API_HOSTNAME
            }
            {
              name: 'API_PORT'
              value: API_PORT
            }
            {
              name: 'NEXT_PUBLIC_API_PROTOCOL'
              value: API_PROTOCOL
            }
            {
              name: 'NEXT_PUBLIC_API_HOSTNAME'
              value: API_HOSTNAME
            }
            {
              name: 'NEXT_PUBLIC_API_PORT'
              value: API_PORT
            }
            {
              name: 'STORAGE_ACCOUNT_NAME'
              value: AZURE_STORAGE_ACCOUNT_NAME
            }
            {
              name: 'AZURE_COSMOS_DB_ENDPOINT'
              value: COSMOS_ENDPOINT
            }
            {
              name: 'AZURE_COSMOS_DB_ID'
              value: COSMOS_DATABASE_NAME
            }
            {
              name: 'AZURE_COSMOS_CONTAINER_ID'
              value: COSMOS_CONTAINER_NAME
            }
            {
              name: 'USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'AZURE_CONTAINER_REGISTRY_ENDPOINT'
              value: AZURE_CONTAINER_REGISTRY_ENDPOINT
            }
          ]
        }
      ]
      // Keep at least one replica running to avoid scale-to-zero
      scale: {
        minReplicas: 1
      }
    }
  }
}

output containerAppId string = containerApp.id
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output containerAppPrincipalId string = deployNew ? containerApp.identity.principalId : ''
