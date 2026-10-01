
param location string
param resourcePrefix string
param storageAccountName string
param appConfigEndpoint string
param cosmosDbEndpoint string
param openAiEndpoint string

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' existing = {
  name: storageAccountName
}


resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${resourcePrefix}-appinsights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

resource hostingPlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: '${resourcePrefix}-plan'
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: '${resourcePrefix}-func-${uniqueString(resourceGroup().id)}'
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: hostingPlan.id
    siteConfig: {
      linuxFxVersion: 'python|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccount.name
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: openAiEndpoint
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'DEPLOY_ENV'
          value: 'production'
        }
        {
          name: 'AZURE_APPCONFIG_ENDPOINT'
          value: appConfigEndpoint
        }
        {
          name: 'COSMOS_DB_URL'
          value: cosmosDbEndpoint
        }

      ]
    }
  }
}

output functionAppPrincipalId string = functionApp.identity.principalId
output functionAppName string = functionApp.name
