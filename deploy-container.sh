#!/bin/bash

# Azure Container Apps Deployment Script for Chuuk Dictionary App
set -e

echo "🚀 Starting Azure Container Apps Deployment..."

# Configuration
RESOURCE_GROUP="rg-chuuk-beta-eastus2"
LOCATION="eastus2"
ACR_NAME="chuukdictregistry"
CONTAINER_APP_NAME="chuuk-dictionary"
IMAGE_NAME="chuuk-dictionary-app"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Container Registry: $ACR_NAME"
echo "  Container App: $CONTAINER_APP_NAME"
echo "  Image: $FULL_IMAGE_NAME"
echo ""

# Get Cosmos DB credentials
echo -e "${BLUE}🔑 Fetching Cosmos DB credentials...${NC}"
COSMOS_DB_NAME="chuuk-dictionary-cosmos"
COSMOS_DB_CONNECTION_STRING=$(az cosmosdb keys list \
    --name $COSMOS_DB_NAME \
    --resource-group $RESOURCE_GROUP \
    --type connection-strings \
    --query "connectionStrings[0].connectionString" \
    --output tsv)

echo -e "${GREEN}✅ Cosmos DB credentials retrieved${NC}"

# Build and push Docker image
echo -e "${BLUE}🔨 Building Docker image...${NC}"
docker build -t $FULL_IMAGE_NAME .

echo -e "${BLUE}📤 Pushing image to Azure Container Registry...${NC}"
az acr login --name $ACR_NAME
docker push $FULL_IMAGE_NAME

echo -e "${GREEN}✅ Image pushed to ACR${NC}"

# Update Container App with new image
echo -e "${BLUE}🔄 Updating Container App with new image...${NC}"
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --image $FULL_IMAGE_NAME \
    --set-env-vars \
        DB_TYPE=cosmos \
        FLASK_ENV=production \
        FLASK_DEBUG=0 \
        COSMOS_CONNECTION_STRING="$COSMOS_DB_CONNECTION_STRING"

echo -e "${GREEN}✅ Container App updated${NC}"

# Get container app details
APP_FQDN=$(az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "properties.configuration.ingress.fqdn" \
    --output tsv)

echo ""
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo ""
echo -e "${BLUE}📱 Application URL:${NC}"
echo "   https://${APP_FQDN}"
echo ""
echo -e "${BLUE}📊 View logs:${NC}"
echo "   az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow"
echo ""
echo -e "${BLUE}🔧 Container App status:${NC}"
echo "   az containerapp show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --query properties.runningStatus"
echo ""
echo -e "${YELLOW}⚠️  Note: It may take a minute for the new revision to deploy.${NC}"
