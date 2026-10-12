
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

output openAiAccountName string = openAi.name
output openAiEndpoint string = openAi.properties.endpoint