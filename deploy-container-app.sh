#!/bin/bash

# Azure Container Apps Deployment Script for Chuuk Dictionary
set -e

echo "🚀 Starting Azure Container Apps Deployment..."

# Configuration
RESOURCE_GROUP="rg-chuuk-beta-eastus2"
LOCATION="eastus2"
CONTAINER_APP_ENV="chuuk-dictionary-env"
CONTAINER_APP_NAME="chuuk-dictionary"
CONTAINER_REGISTRY="chuukdictregistry"
IMAGE_NAME="chuuk-dictionary-app"
IMAGE_TAG="latest"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  Container App: $CONTAINER_APP_NAME"
echo ""

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${YELLOW}⚠️  Azure CLI not found. Please install it first.${NC}"
    exit 1
fi

# Check login
echo -e "${BLUE}🔐 Checking Azure login...${NC}"
if ! az account show &> /dev/null; then
    echo "Please login to Azure:"
    az login
fi

# Register Container Apps provider
echo -e "${BLUE}📦 Registering Azure Container Apps provider...${NC}"
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait
echo -e "${GREEN}✅ Providers registered${NC}"

# Create Azure Container Registry
echo -e "${BLUE}🐳 Creating Container Registry...${NC}"
if ! az acr show --name $CONTAINER_REGISTRY --resource-group $RESOURCE_GROUP &> /dev/null; then
    az acr create \
        --name $CONTAINER_REGISTRY \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --sku Basic \
        --admin-enabled true
    echo -e "${GREEN}✅ Container Registry created${NC}"
else
    echo -e "${GREEN}✅ Container Registry already exists${NC}"
fi

# Build and push image
echo -e "${BLUE}🔨 Building Docker image...${NC}"
az acr build \
    --registry $CONTAINER_REGISTRY \
    --image $IMAGE_NAME:$IMAGE_TAG \
    --file Dockerfile \
    .

echo -e "${GREEN}✅ Image built and pushed${NC}"

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $CONTAINER_REGISTRY --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $CONTAINER_REGISTRY --query passwords[0].value --output tsv)
ACR_LOGIN_SERVER=$(az acr show --name $CONTAINER_REGISTRY --query loginServer --output tsv)

# Generate Flask secret key if not already set
if [ -z "$FLASK_SECRET_KEY" ]; then
    FLASK_SECRET_KEY=$(openssl rand -hex 32)
fi

# Get Google Cloud API Key from .env file
if [ -z "$GOOGLE_CLOUD_API_KEY" ] && [ -f ".env" ]; then
    GOOGLE_CLOUD_API_KEY=$(grep "^GOOGLE_CLOUD_API_KEY=" .env | cut -d '=' -f2)
fi

# Get Cosmos DB credentials
echo -e "${BLUE}🔑 Fetching Cosmos DB credentials...${NC}"
COSMOS_DB_NAME="chuuk-dictionary-cosmos"
COSMOS_DB_KEY=$(az cosmosdb keys list \
    --name $COSMOS_DB_NAME \
    --resource-group $RESOURCE_GROUP \
    --type keys \
    --query "primaryMasterKey" \
    --output tsv)

COSMOS_DB_URI="https://${COSMOS_DB_NAME}.documents.azure.com:443/"
echo -e "${GREEN}✅ Cosmos DB credentials retrieved${NC}"

# Create Container Apps Environment
echo -e "${BLUE}🌍 Creating Container Apps Environment...${NC}"
if ! az containerapp env show --name $CONTAINER_APP_ENV --resource-group $RESOURCE_GROUP &> /dev/null; then
    az containerapp env create \
        --name $CONTAINER_APP_ENV \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION
    echo -e "${GREEN}✅ Container Apps Environment created${NC}"
else
    echo -e "${GREEN}✅ Container Apps Environment already exists${NC}"
fi

# Create or update Container App
echo -e "${BLUE}📱 Deploying Container App...${NC}"
if ! az containerapp show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    # Create new app
    az containerapp create \
        --name $CONTAINER_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --environment $CONTAINER_APP_ENV \
        --image "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" \
        --registry-server $ACR_LOGIN_SERVER \
        --registry-username $ACR_USERNAME \
        --registry-password $ACR_PASSWORD \
        --target-port 8000 \
        --ingress external \
        --cpu 1.0 \
        --memory 2.0Gi \
        --min-replicas 0 \
        --max-replicas 2 \
        --env-vars \
            "DB_TYPE=cosmos" \
            "COSMOS_DB_URI=$COSMOS_DB_URI" \
            "COSMOS_DB_KEY=$COSMOS_DB_KEY" \
            "FLASK_ENV=production" \
            "FLASK_DEBUG=0" \
            "FLASK_SECRET_KEY=$FLASK_SECRET_KEY" \
            "GOOGLE_CLOUD_API_KEY=$GOOGLE_CLOUD_API_KEY"
    echo -e "${GREEN}✅ Container App created${NC}"
else
    # Update existing app
    az containerapp update \
        --name $CONTAINER_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --image "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" \
        --set-env-vars \
            "DB_TYPE=cosmos" \
            "COSMOS_DB_URI=$COSMOS_DB_URI" \
            "COSMOS_DB_KEY=$COSMOS_DB_KEY" \
            "FLASK_ENV=production" \
            "FLASK_DEBUG=0" \
            "FLASK_SECRET_KEY=$FLASK_SECRET_KEY" \
            "GOOGLE_CLOUD_API_KEY=$GOOGLE_CLOUD_API_KEY"
    echo -e "${GREEN}✅ Container App updated${NC}"
fi

# Get the app URL
APP_URL=$(az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query properties.configuration.ingress.fqdn \
    --output tsv)

echo ""
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo ""
echo -e "${BLUE}📱 Application URL:${NC}"
echo "   https://$APP_URL"
echo ""
echo -e "${BLUE}📊 View logs:${NC}"
echo "   az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow"
echo ""
echo -e "${BLUE}🔧 Manage app:${NC}"
echo "   https://portal.azure.com"
echo ""
echo -e "${YELLOW}⚠️  Note: Container Apps scale to zero when idle to save costs.${NC}"
echo -e "${YELLOW}    First request after idle may take 10-15 seconds to start.${NC}"
