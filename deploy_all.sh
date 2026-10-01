#!/bin/bash
set -e

# Prefix must be lowercase alphanumeric for Azure resources
PREFIX="cadefigurinha"

# 1. Provision Cloud Infrastructure (Cosmos, Redis, Function App, App Config)
echo "Setting target subscription..."
az account set --subscription "Azure subscription 1"

echo "Deploying Bicep Infrastructure..."
az deployment sub create \
    --location eastus \
    --template-file infrastructure/main.bicep \
    --parameters resourcePrefix=$PREFIX

# 2. Securely push OpenAI Secret directly from the host environment
if [ -z "$OPENAI_APIKEY" ]; then
    echo "Warning: OPENAI_APIKEY environment variable is not set! Skipping."
else
    echo "Uploading OpenAI Key to Azure App Configuration..."
    APPCONFIG_NAME="${PREFIX}-appconfig"
    az appconfig kv set -n $APPCONFIG_NAME --key "OPENAI_APIKEY" --value "$OPENAI_APIKEY" --yes
fi

# 3. Zip and Deploy the Code
echo "Zipping code..."
rm -f deploy.zip
zip -r deploy.zip . -x "venv/*" -x ".git/*" -x "infrastructure/*" -x "scratch/*" -x "__pycache__/*"

echo "Publishing to Azure Function App..."
# Get the dynamically generated function app name
FUNC_NAME=$(az functionapp list -g "${PREFIX}-rg" --query "[0].name" -o tsv)

az functionapp deployment source config-zip \
    --resource-group "${PREFIX}-rg" \
    --name "$FUNC_NAME" \
    --src deploy.zip \
    --build-remote true

echo "========================================="
echo "Deployment Complete! Your webhook URL is:"
echo "https://${FUNC_NAME}.azurewebsites.net/api/webhook"
echo "========================================="
