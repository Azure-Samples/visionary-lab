param location string
param containerAppEnvName string
param logAnalyticsWorkspaceName string
param deployNew bool = true

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

  }
}

output containerAppEnvId string = containerAppEnv.id
output containerAppDefaultDomain string = containerAppEnv.properties.defaultDomain
