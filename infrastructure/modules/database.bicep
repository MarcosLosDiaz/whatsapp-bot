
param location string
param resourcePrefix string

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: '${resourcePrefix}-cosmos'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosDb
  name: 'WhatsAppBot'
  properties: {
    resource: {
      id: 'WhatsAppBot'
    }
  }
}

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'stickers'
  properties: {
    resource: {
      id: 'stickers'
      partitionKey: {
        paths: [
          '/userId'
        ]
        kind: 'Hash'
      }
    }
  }
}

output cosmosDbAccountName string = cosmosDb.name
