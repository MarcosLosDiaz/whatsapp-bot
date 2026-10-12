#!/bin/bash
set -e

# Prefix must be lowercase alphanumeric for Azure resources
PREFIX="cadefigurinha"

# 1. Provision Cloud Infrastructure (Cosmos DB, OpenAI, Storage, App Config)
echo "Setting target subscription..."
az account set --subscription "Azure subscription 1"

echo "Deploying Bicep Infrastructure..."
az deployment sub create \
    --location eastus \
    --template-file infrastructure/main.bicep \
    --parameters resourcePrefix=$PREFIX

# 2. Securely push secrets directly from the host environment
APPCONFIG_NAME="${PREFIX}-appconfig"

if [ -z "$OPENAI_APIKEY" ]; then
    echo "Warning: OPENAI_APIKEY environment variable is not set! Skipping."
else
    echo "Uploading OpenAI Key to Azure App Configuration..."
    az appconfig kv set -n $APPCONFIG_NAME --key "OPENAI_APIKEY" --value "$OPENAI_APIKEY" --yes
fi

# Meta / WhatsApp secrets (required for the Function App to boot)
if [ -z "$META_APP_SECRET" ]; then
    echo "Warning: META_APP_SECRET not set. You must set it later via: az appconfig kv set -n $APPCONFIG_NAME --key META_APP_SECRET --value <secret> --yes"
else
    az appconfig kv set -n $APPCONFIG_NAME --key "META_APP_SECRET" --value "$META_APP_SECRET" --yes
fi

if [ -z "$META_GRAPH_TOKEN" ]; then
    echo "Warning: META_GRAPH_TOKEN not set. You must set it later via: az appconfig kv set -n $APPCONFIG_NAME --key META_GRAPH_TOKEN --value <token> --yes"
else
    az appconfig kv set -n $APPCONFIG_NAME --key "META_GRAPH_TOKEN" --value "$META_GRAPH_TOKEN" --yes
fi

if [ -z "$META_PHONE_ID" ]; then
    echo "Warning: META_PHONE_ID not set. You must set it later via: az appconfig kv set -n $APPCONFIG_NAME --key META_PHONE_ID --value <id> --yes"
else
    az appconfig kv set -n $APPCONFIG_NAME --key "META_PHONE_ID" --value "$META_PHONE_ID" --yes
fi

if [ -z "$META_VERIFY_TOKEN" ]; then
    echo "Warning: META_VERIFY_TOKEN not set (will default to 'default_verify_token'). You can set it via: az appconfig kv set -n $APPCONFIG_NAME --key META_VERIFY_TOKEN --value <token> --yes"
else
    az appconfig kv set -n $APPCONFIG_NAME --key "META_VERIFY_TOKEN" --value "$META_VERIFY_TOKEN" --yes
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
