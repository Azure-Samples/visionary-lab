param location string
param containerAppName string
param containerAppEnvId string
param DOCKER_IMAGE string
param deployNew bool = true
param azdServiceName string = ''

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
param IMAGEGEN_DEPLOYMENT string = 'gpt-image-1-5'
param IMAGEGEN_15_DEPLOYMENT string = ''
param IMAGEGEN_1_MINI_DEPLOYMENT string = ''
param SORA_DEPLOYMENT string = 'sora'
param FLUX_KONTEXT_DEPLOYMENT string = ''

// Azure Blob Storage (managed identity — no keys)
param AZURE_BLOB_SERVICE_URL string
param AZURE_STORAGE_ACCOUNT_NAME string
param AZURE_BLOB_IMAGE_CONTAINER string = 'images'

param targetPort int = 80
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
      secrets: concat(
        AZURE_CONTAINER_REGISTRY_ENDPOINT != '' ? [
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
              name: 'AI_FOUNDRY_ENDPOINT'
              value: AI_FOUNDRY_ENDPOINT
            }
            {
              name: 'LLM_DEPLOYMENT'
              value: LLM_DEPLOYMENT
            }
            {
              name: 'IMAGEGEN_DEPLOYMENT'
              value: IMAGEGEN_DEPLOYMENT
            }
            {
              name: 'IMAGEGEN_15_DEPLOYMENT'
              value: IMAGEGEN_15_DEPLOYMENT
            }
            {
              name: 'IMAGEGEN_1_MINI_DEPLOYMENT'
              value: IMAGEGEN_1_MINI_DEPLOYMENT
            }
            {
              name: 'SORA_DEPLOYMENT'
              value: SORA_DEPLOYMENT
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
          ]
        }
      ]
      scale: {
        minReplicas: 1
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

output containerAppId string = containerApp.id
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output containerAppPrincipalId string = deployNew ? containerApp.identity.principalId : ''
