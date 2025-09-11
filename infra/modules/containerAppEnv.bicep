@description('Location for all resources')
param location string
@description('Name of the Container App Environment')
param containerAppEnvName string
@description('Name of the Log Analytics workspace')
param logAnalyticsWorkspaceName string
@description('Whether to deploy new resources')
param deployNew bool = true
@description('Subnet ID for VNet integration (required for private Cosmos DB access)')
param subnetId string

// Subnet ID validation
var hasSubnetId = length(subnetId) > 0

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  location: location
  name: logAnalyticsWorkspaceName
  properties: {
  }
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2025-01-01' = if(deployNew) {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
    // VNet integration for private Cosmos DB access (only if subnet provided)
    vnetConfiguration: hasSubnetId ? {
      infrastructureSubnetId: subnetId
      internal: false // Set to true for completely internal environment  
    } : null
    zoneRedundant: false // Can be enabled for production
  }
}

output containerAppEnvId string = containerAppEnv.id
output containerAppDefaultDomain string = containerAppEnv.properties.defaultDomain
