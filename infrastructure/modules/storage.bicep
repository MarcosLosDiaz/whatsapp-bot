
param location string
param resourcePrefix string

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: take('${resourcePrefix}stg${uniqueString(resourceGroup().id)}', 24)
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  parent: blobService
  name: 'stickers'
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
}

resource queueStickers 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: queueService
  name: 'incoming-stickers'
}

resource queueQueries 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: queueService
  name: 'incoming-queries'
}

output storageAccountName string = storageAccount.name
