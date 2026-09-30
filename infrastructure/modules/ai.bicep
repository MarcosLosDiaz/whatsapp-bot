
param location string
param resourcePrefix string

resource openAi 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${resourcePrefix}-openai'
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: '${resourcePrefix}-openai'
  }
}

resource gpt4oMini 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAi
  name: 'gpt-4o-mini'
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-mini'
      version: '2024-07-18'
    }
  }
}

resource embeddings 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAi
  name: 'text-embedding-3-small'
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
}

#disable-next-line BCP081
resource bingSearch 'Microsoft.Bing/accounts@2020-06-10' = {
  name: '${resourcePrefix}-bing'
  location: 'global'
  kind: 'Bing.Search.v7'
  sku: {
    name: 'F1'
  }
}

output openAiAccountName string = openAi.name
output bingSearchName string = bingSearch.name
