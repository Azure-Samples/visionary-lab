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

// Pin to a stable API version
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2021-06-01' = {
  location: location
  name: logAnalyticsWorkspaceName
  properties: {
  }
}

// Pin to a stable API version
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' = if(deployNew) {
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
      internal: false // External access enabled
      // Platform reserved CIDR must be between /24 and /12 and MUST NOT overlap with your VNet ranges
      // Use an RFC1918 range distinct from your VNet (e.g., 172.16.0.0/16)
      platformReservedCidr: '172.16.0.0/16'
      platformReservedDnsIP: '172.16.0.10'
    } : null
    zoneRedundant: false // Can be enabled for production
  }
}

output containerAppEnvId string = containerAppEnv.id
output containerAppDefaultDomain string = containerAppEnv.properties.defaultDomain
