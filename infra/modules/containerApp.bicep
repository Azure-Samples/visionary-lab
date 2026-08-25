param location string
param containerAppName string
param containerAppEnvId string
param DOCKER_IMAGE string
param deployNew bool = true
param azdServiceName string = ''
param customDomainName string = ''
param certificateId string = ''

// Easy Auth configuration (set enableAuth=true for frontend)
param enableAuth bool = false
@secure()
param authClientId string = ''
@secure()
param authClientSecret string = ''
param authIssuer string = ''

// AI Foundry endpoint (unified for all AI services)
param AI_FOUNDRY_ENDPOINT string = ''
// Model deployment names
param LLM_DEPLOYMENT string = 'gpt-4o'
param IMAGEGEN_2_DEPLOYMENT string = 'gpt-image-2'
param FLUX_KONTEXT_DEPLOYMENT string = ''

// Azure Blob Storage (managed identity — no keys)
param AZURE_BLOB_SERVICE_URL string
param AZURE_STORAGE_ACCOUNT_NAME string
param AZURE_BLOB_IMAGE_CONTAINER string = 'images'
param AZURE_STORAGE_QUEUE_URL string = ''
param AZURE_STORAGE_QUEUE_NAME string = 'image-generation-jobs'
param AZURE_STORAGE_POISON_QUEUE_NAME string = 'image-generation-jobs-poison'
param CDN_BLOB_URL string = ''
param CORS_ALLOWED_ORIGINS string = ''
param IMAGE_JOB_ROLE string = ''
param IMAGE_JOB_MODE string = ''

@minValue(0)
param IMAGE_JOB_CONCURRENCY int = 0

@description('Expose the Container App through HTTP ingress')
param enableIngress bool = true

@description('Expose HTTP ingress outside the Container Apps environment')
param externalIngress bool = true

@description('Configure the HTTP readiness probe used by web-facing apps')
param enableHttpProbe bool = true

@description('Enable event-driven scaling from the image-generation Storage Queue')
param enableQueueScaleRule bool = false

@minValue(0)
@description('Minimum number of Container App replicas')
param minReplicas int = 1

@minValue(1)
@description('Maximum number of Container App replicas')
param maxReplicas int = 10

@minValue(1)
@description('Queued messages per replica for the Storage Queue scale rule')
param queueScaleTargetLength int = 1

param targetPort int = 80
@minValue(1)
param containerCpu int = 1
param containerMemory string = '2Gi'
param API_PROTOCOL string = 'http'
param API_HOSTNAME string = 'localhost'
param API_PORT string = '80'

// Cosmos DB (managed identity — no keys)
param COSMOS_ENDPOINT string = ''
param COSMOS_DATABASE_NAME string = ''
param COSMOS_CONTAINER_NAME string = ''

// Azure Container Registry
param AZURE_CONTAINER_REGISTRY_ENDPOINT string = ''
@secure()
param AZURE_CONTAINER_REGISTRY_USERNAME string = ''
@secure()
param AZURE_CONTAINER_REGISTRY_PASSWORD string = ''

@description('User-assigned identity resource ID used to pull images from ACR')
param registryIdentityResourceId string = ''

resource containerApp 'Microsoft.App/containerApps@2025-01-01' = if(deployNew) {
  name: containerAppName
  location: location
  tags: azdServiceName != '' ? {
    'azd-service-name': azdServiceName
  } : {}
  identity: registryIdentityResourceId != '' ? {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${registryIdentityResourceId}': {}
    }
  } : {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppEnvId
    configuration: union({
      registries: AZURE_CONTAINER_REGISTRY_ENDPOINT != '' ? [
        registryIdentityResourceId != '' ? {
          server: AZURE_CONTAINER_REGISTRY_ENDPOINT
          identity: registryIdentityResourceId
        } : {
          server: AZURE_CONTAINER_REGISTRY_ENDPOINT
          username: AZURE_CONTAINER_REGISTRY_USERNAME
          passwordSecretRef: 'acr-password'
        }
      ] : []
      secrets: concat(
        AZURE_CONTAINER_REGISTRY_ENDPOINT != '' && registryIdentityResourceId == '' ? [
          {
            name: 'acr-password'
            value: AZURE_CONTAINER_REGISTRY_PASSWORD
          }
        ] : [],
        enableAuth ? [
          {
            name: 'microsoft-provider-authentication-secret'
            value: authClientSecret
          }
        ] : []
      )
    }, enableIngress ? {
      ingress: {
        external: externalIngress
        targetPort: targetPort
        transport: 'Auto'
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
        customDomains: customDomainName != '' ? [
          {
            name: customDomainName
            certificateId: certificateId
            bindingType: certificateId != '' ? 'SniEnabled' : 'Disabled'
          }
        ] : []
      }
    } : {})
    template: {
      containers: [
        {
          name: containerAppName
          image: DOCKER_IMAGE
          resources: {
            cpu: containerCpu
            memory: containerMemory
          }
          probes: enableHttpProbe ? [
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
          ] : []
          env: concat([
            {
              name: 'AI_FOUNDRY_ENDPOINT'
              value: AI_FOUNDRY_ENDPOINT
            }
            {
              name: 'LLM_DEPLOYMENT'
              value: LLM_DEPLOYMENT
            }
            {
              name: 'IMAGEGEN_2_DEPLOYMENT'
              value: IMAGEGEN_2_DEPLOYMENT
            }
            {
              name: 'FLUX_KONTEXT_DEPLOYMENT'
              value: FLUX_KONTEXT_DEPLOYMENT
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
              name: 'AZURE_CONTAINER_REGISTRY_ENDPOINT'
              value: AZURE_CONTAINER_REGISTRY_ENDPOINT
            }
            {
              name: 'CDN_BLOB_URL'
              value: CDN_BLOB_URL
            }
          ], AZURE_STORAGE_QUEUE_URL != '' ? [
            {
              name: 'AZURE_STORAGE_QUEUE_URL'
              value: AZURE_STORAGE_QUEUE_URL
            }
            {
              name: 'AZURE_STORAGE_QUEUE_NAME'
              value: AZURE_STORAGE_QUEUE_NAME
            }
            {
              name: 'AZURE_STORAGE_POISON_QUEUE_NAME'
              value: AZURE_STORAGE_POISON_QUEUE_NAME
            }
          ] : [], CORS_ALLOWED_ORIGINS != '' ? [
            {
              name: 'CORS_ALLOWED_ORIGINS'
              value: CORS_ALLOWED_ORIGINS
            }
          ] : [], IMAGE_JOB_ROLE != '' ? [
            {
              name: 'IMAGE_JOB_ROLE'
              value: IMAGE_JOB_ROLE
            }
          ] : [], IMAGE_JOB_MODE != '' ? [
            {
              name: 'IMAGE_JOB_MODE'
              value: IMAGE_JOB_MODE
            }
          ] : [], IMAGE_JOB_CONCURRENCY > 0 ? [
            {
              name: 'IMAGE_JOB_CONCURRENCY'
              value: string(IMAGE_JOB_CONCURRENCY)
            }
          ] : [])
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: enableQueueScaleRule ? [
          {
            name: 'image-generation-queue'
            custom: {
              type: 'azure-queue'
              metadata: {
                accountName: AZURE_STORAGE_ACCOUNT_NAME
                queueName: AZURE_STORAGE_QUEUE_NAME
                queueLength: string(queueScaleTargetLength)
              }
              identity: 'system'
            }
          }
        ] : []
      }
    }
  }
}

// Easy Auth configuration (only when enableAuth is true)
resource authConfig 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (deployNew && enableAuth) {
  name: 'current'
  parent: containerApp
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
      excludedPaths: [
        '/manifest.json'
        '/sw.js'
        '/favicon.ico'
        '/_next/*'
      ]
    }
    login: {
      preserveUrlFragmentsForLogins: true
    }
    identityProviders: {
      azureActiveDirectory: {
        registration: {
          clientId: authClientId
          clientSecretSettingName: 'microsoft-provider-authentication-secret'
          openIdIssuer: authIssuer
        }
        validation: {
          allowedAudiences: [
            'api://${authClientId}'
            authClientId
          ]
        }
      }
    }
  }
}

output containerAppId string = deployNew ? containerApp!.id : ''
output containerAppFqdn string = deployNew && enableIngress ? containerApp!.properties.configuration.ingress.fqdn : ''
output containerAppPrincipalId string = deployNew ? containerApp!.identity.principalId : ''
