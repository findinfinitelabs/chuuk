---
name: azure-container-deployment
description: Deploy containerized applications to Azure Container Apps with Cosmos DB, Key Vault, ACR integration, and multi-container orchestration. Use when deploying the Chuuk Dictionary app, managing Azure infrastructure, or setting up production environments.
---

# Azure Container Deployment

## Overview

Deploy and manage the Chuuk Dictionary application on Azure using Container Apps, Azure Container Registry (ACR), Cosmos DB, and Key Vault. Supports multi-container deployments including the main Flask application and Ollama for LLM-based translation.

## Architecture

```text
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Azure Static  │────▶│   Azure Container │────▶│   Azure Cosmos  │
│   Web Apps      │     │   Apps            │     │   DB            │
│   (React)       │     │   (Flask + Ollama)│     │   (MongoDB API) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌──────────────────┐
                        │   Azure Key      │
                        │   Vault          │
                        └──────────────────┘
```

## Configuration

### Environment Variables

```bash
# Resource configuration
RESOURCE_GROUP=rg-chuuk-beta-eastus2
LOCATION=eastus2
CONTAINER_APP_ENV=chuuk-dictionary-env
ACR_NAME=chuukdictregistry
MAIN_APP_NAME=chuuk-dictionary
OLLAMA_APP_NAME=chuuk-ollama
COSMOS_DB_NAME=chuuk-dictionary-cosmos
KEY_VAULT_NAME=chuuk-kv-beta
```

## Deployment Script Reference

### deploy-chuuk.sh Structure

```bash
#!/bin/bash
set -euo pipefail

# Configuration
RESOURCE_GROUP=${RESOURCE_GROUP:-rg-chuuk-beta-eastus2}
LOCATION=${LOCATION:-eastus2}
ACR_NAME=${ACR_NAME:-chuukdictregistry}
MAIN_APP_NAME=${MAIN_APP_NAME:-chuuk-dictionary}

# Logging helpers
log() { printf "${BLUE}%s${NC}\n" "$1"; }
success() { printf "${GREEN}%s${NC}\n" "$1"; }
warn() { printf "${YELLOW}%s${NC}\n" "$1"; }
die() { echo "$1" >&2; exit 1; }

# Ensure Azure CLI logged in
ensure_login() {
  if ! az account show >/dev/null 2>&1; then
    az login
  fi
}
```

## Core Operations

### 1. Resource Group Setup

```bash
# Create resource group
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION"
```

### 2. Azure Container Registry

```bash
# Create ACR
az acr create \
  --name "$ACR_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --sku Basic \
  --admin-enabled true

# Get ACR credentials
ACR_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

# Login to ACR
az acr login --name "$ACR_NAME"

# Build and push main app image
docker build -t "${ACR_SERVER}/${MAIN_IMAGE}:${IMAGE_TAG}" .
docker push "${ACR_SERVER}/${MAIN_IMAGE}:${IMAGE_TAG}"

# Build and push Ollama image
docker build -f Dockerfile.ollama -t "${ACR_SERVER}/${OLLAMA_IMAGE}:${IMAGE_TAG}" .
docker push "${ACR_SERVER}/${OLLAMA_IMAGE}:${IMAGE_TAG}"
```

### 3. Cosmos DB Setup

```bash
# Create Cosmos DB with MongoDB API
az cosmosdb create \
  --name "$COSMOS_DB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --kind MongoDB \
  --capabilities EnableServerless \
  --locations regionName="$LOCATION" \
  --default-consistency-level Session

# Get connection string
COSMOS_CONNECTION_STRING=$(az cosmosdb keys list \
  --name "$COSMOS_DB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --type connection-strings \
  --query "connectionStrings[0].connectionString" -o tsv)
```

### 4. Key Vault Setup

```bash
# Create Key Vault
az keyvault create \
  --name "$KEY_VAULT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --enable-rbac-authorization true

# Store secrets
az keyvault secret set \
  --vault-name "$KEY_VAULT_NAME" \
  --name "cosmos-connection-string" \
  --value "$COSMOS_CONNECTION_STRING"

az keyvault secret set \
  --vault-name "$KEY_VAULT_NAME" \
  --name "flask-secret-key" \
  --value "$(openssl rand -hex 32)"
```

### 5. Container Apps Environment

```bash
# Create Container Apps environment
az containerapp env create \
  --name "$CONTAINER_APP_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION"

# Get environment ID
ENV_ID=$(az containerapp env show \
  --name "$CONTAINER_APP_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --query id -o tsv)
```

### 6. Deploy Main Application

```bash
# Deploy main Flask app
az containerapp create \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$CONTAINER_APP_ENV" \
  --image "${ACR_SERVER}/${MAIN_IMAGE}:${IMAGE_TAG}" \
  --registry-server "$ACR_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 1.0 \
  --memory 2Gi \
  --env-vars \
    "DB_TYPE=cosmos" \
    "COSMOS_DB_URI=secretref:cosmos-connection-string" \
    "FLASK_ENV=production"
```

### 7. Deploy Ollama Service

```bash
# Deploy Ollama container (internal only)
az containerapp create \
  --name "$OLLAMA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$CONTAINER_APP_ENV" \
  --image "${ACR_SERVER}/${OLLAMA_IMAGE}:${IMAGE_TAG}" \
  --registry-server "$ACR_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --target-port 11434 \
  --ingress internal \
  --min-replicas 0 \
  --max-replicas 1 \
  --cpu 2.0 \
  --memory 4Gi
```

## Update Operations

### Update Container Image

```bash
# Build new image
docker build -t "${ACR_SERVER}/${MAIN_IMAGE}:${IMAGE_TAG}" .
docker push "${ACR_SERVER}/${MAIN_IMAGE}:${IMAGE_TAG}"

# Update container app
az containerapp update \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --image "${ACR_SERVER}/${MAIN_IMAGE}:${IMAGE_TAG}"
```

### Scale Application

```bash
# Scale up
az containerapp update \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --min-replicas 2 \
  --max-replicas 5

# Scale down (cost saving)
az containerapp update \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --min-replicas 0 \
  --max-replicas 1
```

### Update Environment Variables

```bash
az containerapp update \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "NEW_VAR=value"
```

## Monitoring & Logs

### View Logs

```bash
# Stream logs
az containerapp logs show \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --follow

# View recent logs
az containerapp logs show \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --tail 100
```

### Check Status

```bash
# Get app URL
az containerapp show \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv

# Check replicas
az containerapp revision list \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[].{name:name, replicas:replicas, active:active}"
```

## Cost Optimization

### Serverless Cosmos DB

```bash
# Use serverless tier for development
az cosmosdb create \
  --name "$COSMOS_DB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --capabilities EnableServerless
```

### Container Apps Scaling

```bash
# Scale to zero when not in use
az containerapp update \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --min-replicas 0
```

## Troubleshooting

### Common Issues

1. **Container won't start**: Check logs and ensure all env vars are set
2. **Database connection failed**: Verify Cosmos DB connection string
3. **Image pull failed**: Check ACR credentials
4. **Memory issues**: Increase container memory allocation

### Debug Commands

```bash
# Check container app details
az containerapp show \
  --name "$MAIN_APP_NAME" \
  --resource-group "$RESOURCE_GROUP"

# Check environment
az containerapp env show \
  --name "$CONTAINER_APP_ENV" \
  --resource-group "$RESOURCE_GROUP"

# Check secrets
az keyvault secret list --vault-name "$KEY_VAULT_NAME"
```

## Best Practices

1. **Use managed identity** for Azure resource authentication
2. **Store secrets in Key Vault**, never in environment variables
3. **Enable auto-scaling** based on HTTP traffic
4. **Use staging slots** for zero-downtime deployments
5. **Monitor costs** with Azure Cost Management
6. **Enable logging** to Log Analytics workspace

## Dependencies

- Azure CLI (`az`)
- Docker
- Azure subscription with appropriate permissions
- ACR, Cosmos DB, Key Vault, Container Apps resource providers enabled
