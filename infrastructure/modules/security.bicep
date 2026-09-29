
param functionAppPrincipalId string
param storageAccountName string
param cosmosDbAccountName string
param openAiAccountName string

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' existing = {
  name: storageAccountName
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = {
  name: cosmosDbAccountName
}

resource openAi 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: openAiAccountName
}

// Storage Blob Data Contributor
resource blobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionAppPrincipalId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Queue Data Contributor
resource queueRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionAppPrincipalId, '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services OpenAI User
resource openAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, functionAppPrincipalId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: openAi
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB Built-in Data Contributor (00000000-0000-0000-0000-000000000002) is assigned differently, typically via sqlRoleAssignments.
resource sqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-04-15' = {
  parent: cosmosDb
  name: guid(cosmosDb.id, functionAppPrincipalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmosDb.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: functionAppPrincipalId
    scope: cosmosDb.id
  }
}
