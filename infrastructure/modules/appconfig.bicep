param location string
param resourcePrefix string

resource appConfig 'Microsoft.AppConfiguration/configurationStores@2023-03-01' = {
  name: '${resourcePrefix}-appconfig'
  location: location
  sku: {
    name: 'free'
  }
  properties: {
    disableLocalAuth: false
  }
}

output appConfigName string = appConfig.name
output appConfigEndpoint string = appConfig.properties.endpoint
