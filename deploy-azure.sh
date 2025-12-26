#!/bin/bash

# Azure Deployment Script for Chuuk Dictionary App
# This script deploys the Flask API to Azure App Service

set -e

echo "🚀 Starting Azure Deployment..."

# Configuration
RESOURCE_GROUP="rg-chuuk-beta-eastus2"
LOCATION="eastus2"
APP_SERVICE_PLAN="chuuk-dictionary-plan"
WEB_APP_NAME="chuuk-dictionary-api"
PYTHON_VERSION="3.11"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  Web App: $WEB_APP_NAME"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${YELLOW}⚠️  Azure CLI not found. Installing...${NC}"
    curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
fi

# Login check
echo -e "${BLUE}🔐 Checking Azure login status...${NC}"
if ! az account show &> /dev/null; then
    echo "Please login to Azure:"
    az login
fi

# Create App Service Plan (if it doesn't exist)
echo -e "${BLUE}📦 Creating App Service Plan...${NC}"
if ! az appservice plan show --name $APP_SERVICE_PLAN --resource-group $RESOURCE_GROUP &> /dev/null; then
    az appservice plan create \
        --name $APP_SERVICE_PLAN \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --sku F1 \
        --is-linux
    echo -e "${GREEN}✅ App Service Plan created (Free tier)${NC}"
else
    echo -e "${GREEN}✅ App Service Plan already exists${NC}"
fi

# Create Web App (if it doesn't exist)
echo -e "${BLUE}🌐 Creating Web App...${NC}"
if ! az webapp show --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    az webapp create \
        --name $WEB_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --plan $APP_SERVICE_PLAN \
        --runtime "PYTHON:$PYTHON_VERSION"
    echo -e "${GREEN}✅ Web App created${NC}"
else
    echo -e "${GREEN}✅ Web App already exists${NC}"
fi

# Get Cosmos DB connection details
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

# Configure App Settings
echo -e "${BLUE}⚙️  Configuring application settings...${NC}"
az webapp config appsettings set \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings \
        DB_TYPE=cosmos \
        COSMOS_DB_URI="$COSMOS_DB_URI" \
        COSMOS_DB_KEY="$COSMOS_DB_KEY" \
        FLASK_ENV=production \
        FLASK_DEBUG=0 \
        SCM_DO_BUILD_DURING_DEPLOYMENT=true \
        ENABLE_ORYX_BUILD=true \
        POST_BUILD_COMMAND="pip install -r requirements.txt" \
    --output none

echo -e "${GREEN}✅ Application settings configured${NC}"

# Configure startup command
echo -e "${BLUE}🚀 Configuring startup command...${NC}"
az webapp config set \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 4 app:app" \
    --output none

echo -e "${GREEN}✅ Startup command configured${NC}"

# Enable logging
echo -e "${BLUE}📝 Enabling application logging...${NC}"
az webapp log config \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --application-logging filesystem \
    --detailed-error-messages true \
    --failed-request-tracing true \
    --level information \
    --output none

echo -e "${GREEN}✅ Logging enabled${NC}"

# Deploy application
echo -e "${BLUE}📤 Deploying application code...${NC}"
echo "This may take several minutes..."

# Build frontend first
echo -e "${BLUE}🔨 Building React frontend...${NC}"
cd frontend
npm install
npm run build
cd ..

# Deploy using zip deploy
echo -e "${BLUE}📦 Creating deployment package...${NC}"
zip -r deploy.zip . -x "*.git*" "*node_modules*" "*__pycache__*" "*.pyc" "*frontend/node_modules*" "*venv*" "*logs/*"

az webapp deployment source config-zip \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --src deploy.zip

rm deploy.zip

echo -e "${GREEN}✅ Application deployed${NC}"

# Get the app URL
APP_URL="https://${WEB_APP_NAME}.azurewebsites.net"

echo ""
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo ""
echo -e "${BLUE}📱 Application URL:${NC}"
echo "   $APP_URL"
echo ""
echo -e "${BLUE}📊 View logs:${NC}"
echo "   az webapp log tail --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo -e "${BLUE}🔧 Manage app:${NC}"
echo "   https://portal.azure.com"
echo ""
echo -e "${YELLOW}⚠️  Note: It may take a few minutes for the app to start up.${NC}"
