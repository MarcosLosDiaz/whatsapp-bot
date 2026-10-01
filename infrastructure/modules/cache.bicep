param location string
param resourcePrefix string

resource redisEnterprise 'Microsoft.Cache/redisEnterprise@2023-11-01' = {
  name: '${resourcePrefix}-redis'
  location: location
  sku: {
    name: 'Enterprise_E10'
    capacity: 2
  }
}

resource redisEnterpriseDatabase 'Microsoft.Cache/redisEnterprise/databases@2023-11-01' = {
  parent: redisEnterprise
  name: 'default'
  properties: {
    clientProtocol: 'Encrypted'
    port: 10000
    clusteringPolicy: 'EnterpriseCluster'
    evictionPolicy: 'NoEviction'
    modules: [
      {
        name: 'RediSearch'
      }
    ]
  }
}

output redisName string = redisEnterprise.name