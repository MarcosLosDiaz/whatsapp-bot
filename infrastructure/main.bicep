
targetScope = 'subscription'

param location string = 'eastus'
param cosmosLocation string = 'eastus2'
param functionLocation string = 'centralus'
param resourcePrefix string = 'cadefigurinha'

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${resourcePrefix}-rg'
  location: location
}

module storage 'modules/storage.bicep' = {
  scope: rg
  name: 'storageDeploy'
  params: {
    location: location
    resourcePrefix: resourcePrefix
  }
}

module ai 'modules/ai.bicep' = {
  scope: rg
  name: 'aiDeploy'
  params: {
    location: location
    resourcePrefix: resourcePrefix
  }
}

module database 'modules/database.bicep' = {
  scope: rg
  name: 'databaseDeploy'
  params: {
    location: cosmosLocation
    resourcePrefix: resourcePrefix
  }
}


module appconfig 'modules/appconfig.bicep' = {
  scope: rg
  name: 'appconfigDeploy'
  params: {
    location: location
    resourcePrefix: resourcePrefix
  }
}

module compute 'modules/compute.bicep' = {
  scope: rg
  name: 'computeDeploy'
  params: {
    location: location
    functionLocation: functionLocation
    resourcePrefix: resourcePrefix
    storageAccountName: storage.outputs.storageAccountName
    appConfigEndpoint: appconfig.outputs.appConfigEndpoint
    cosmosDbEndpoint: database.outputs.cosmosDbEndpoint
    openAiEndpoint: ''
  }
}

module security 'modules/security.bicep' = {
  scope: rg
  name: 'securityDeploy'
  params: {
    functionAppPrincipalId: compute.outputs.functionAppPrincipalId
    storageAccountName: storage.outputs.storageAccountName
    cosmosDbAccountName: database.outputs.cosmosDbAccountName
    openAiAccountName: ai.outputs.openAiAccountName
    appConfigName: appconfig.outputs.appConfigName
  }
}

