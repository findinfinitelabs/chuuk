#!/bin/bash
set -e

# Configuration
RESOURCE_GROUP="rg-chuuk-beta-eastus2"
LOCATION="eastus2"
REGISTRY_NAME="chuukdictregistry"
ENVIRONMENT_NAME="chuuk-dictionary-env"
OLLAMA_APP_NAME="chuuk-ollama"
IMAGE_NAME="chuuk-ollama"
IMAGE_TAG="latest"

echo "======================================"
echo "Deploying Ollama Container App"
echo "======================================"

# Check if logged in to Azure
echo "Checking Azure login status..."
az account show > /dev/null 2>&1 || {
    echo "Not logged in to Azure. Please run 'az login' first."
    exit 1
}

echo "✓ Logged in to Azure"

# Build and push Ollama image to ACR
echo ""
echo "Building and pushing Ollama Docker image to ACR..."
az acr build \
    --registry $REGISTRY_NAME \
    --image $IMAGE_NAME:$IMAGE_TAG \
    --file Dockerfile.ollama \
    .

echo "✓ Ollama image built and pushed to ACR"

# Check if Container App already exists
echo ""
echo "Checking if Ollama Container App exists..."
if az containerapp show --name $OLLAMA_APP_NAME --resource-group $RESOURCE_GROUP > /dev/null 2>&1; then
    echo "Updating existing Ollama Container App..."
    az containerapp update \
        --name $OLLAMA_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --image $REGISTRY_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG \
        --cpu 2.0 \
        --memory 4Gi
    
    echo "✓ Ollama Container App updated successfully"
else
    echo "Creating new Ollama Container App..."
    az containerapp create \
        --name $OLLAMA_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --environment $ENVIRONMENT_NAME \
        --image $REGISTRY_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG \
        --target-port 11434 \
        --ingress internal \
        --cpu 2.0 \
        --memory 4Gi \
        --min-replicas 1 \
        --max-replicas 1 \
        --registry-server $REGISTRY_NAME.azurecr.io
    
    echo "✓ Ollama Container App created successfully"
fi

# Get the internal FQDN
echo ""
echo "Getting Ollama service URL..."
OLLAMA_FQDN=$(az containerapp show \
    --name $OLLAMA_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "properties.configuration.ingress.fqdn" \
    -o tsv)

echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
echo "Ollama Service URL: https://$OLLAMA_FQDN"
echo ""
echo "To use this in your main app, set the environment variable:"
echo "OLLAMA_BASE_URL=https://$OLLAMA_FQDN"
echo ""
echo "Next steps:"
echo "1. Update your main app's environment variables"
echo "2. Redeploy the main app with: bash deploy-container-app.sh"
