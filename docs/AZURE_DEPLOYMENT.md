# Azure Deployment Guide for Chuuk Dictionary OCR

This guide covers deploying your Chuuk Dictionary OCR application to Azure using Cosmos DB for production.

## 🏗️ Azure Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Azure Static  │────▶│   Azure App      │────▶│   Azure Cosmos  │
│   Web Apps      │     │   Service        │     │   DB            │
│   (React)       │     │   (Flask API)    │     │   (Database)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## 📋 Prerequisites

1. **Azure CLI** installed and logged in
2. **Azure subscription** with sufficient credits
3. **Resource group** created
4. **Domain name** (optional, for custom domain)

## 🚀 Deployment Steps

### 1. Set up Cosmos DB

```bash
# Create Cosmos DB account
az cosmosdb create \
  --name chuuk-dictionary-db \
  --resource-group your-resource-group \
  --kind MongoDB \
  --locations regionName=eastus \
  --enable-free-tier true

# Get connection string
az cosmosdb keys list \
  --name chuuk-dictionary-db \
  --resource-group your-resource-group \
  --type connection-strings
```

### 2. Deploy Flask API to Azure App Service

```bash
# Create App Service plan
az appservice plan create \
  --name chuuk-dictionary-plan \
  --resource-group your-resource-group \
  --sku B1 \
  --is-linux

# Create web app
az webapp create \
  --name chuuk-dictionary-api \
  --resource-group your-resource-group \
  --plan chuuk-dictionary-plan \
  --runtime "PYTHON:3.11"

# Configure app settings
az webapp config appsettings set \
  --name chuuk-dictionary-api \
  --resource-group your-resource-group \
  --settings \
    DB_TYPE=cosmos \
    COSMOS_DB_URI="your-cosmos-connection-string" \
    COSMOS_DB_KEY="your-cosmos-key" \
    FLASK_ENV=production
```

### 3. Deploy React App to Azure Static Web Apps

```bash
# Build the React app
cd frontend
npm run build

# Create Static Web App
az staticwebapp create \
  --name chuuk-dictionary-frontend \
  --resource-group your-resource-group \
  --source . \
  --location "East US 2" \
  --branch main \
  --app-location "frontend" \
  --output-location "dist"
```

### 4. Configure Environment Variables

Update your production `.env` file:

```env
# Production Environment
DB_TYPE=cosmos
COSMOS_DB_URI=https://chuuk-dictionary-db.documents.azure.com:443/
COSMOS_DB_KEY=your-primary-key-from-azure

# API Configuration
API_BASE_URL=https://chuuk-dictionary-api.azurewebsites.net

# Flask Production Settings
FLASK_ENV=production
FLASK_DEBUG=0
```

## 🔧 Local Development with Cosmos DB Emulator

For local development with Cosmos DB compatibility:

### 1. Install Cosmos DB Emulator

**Windows:**
```bash
# Download and install from Microsoft
# https://docs.microsoft.com/en-us/azure/cosmos-db/local-emulator
```

**macOS/Linux (using Docker):**
```bash
docker run -p 8081:8081 -p 10251:10251 -p 10252:10252 -p 10253:10253 -p 10254:10254 \
  mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:latest
```

### 2. Update Environment

```bash
# Set environment for Cosmos DB
export DB_TYPE=cosmos

# Or in PowerShell
$env:DB_TYPE="cosmos"

# Start services with Cosmos DB
./run.sh start
```

### 3. Access Cosmos DB Data Explorer

Open https://localhost:8081/_explorer/index.html to view your data.

## 🛠️ Database Migration

To migrate from MongoDB to Cosmos DB:

### 1. Export from MongoDB

```python
# scripts/export_mongodb.py
from src.database.dictionary_db import DictionaryDB
import json

db = DictionaryDB("mongodb://localhost:27017/")
entries = list(db.dictionary_collection.find({}))

with open('mongodb_export.json', 'w') as f:
    json.dump(entries, f, default=str, indent=2)
```

### 2. Import to Cosmos DB

```python
# scripts/import_cosmosdb.py
from src.database.db_factory import get_database_client
from azure.cosmos import exceptions
import json
import os

os.environ['DB_TYPE'] = 'cosmos'
client = get_database_client()
database = client.get_database_client('chuuk_dictionary')
container = database.get_container_client('dictionary_entries')

with open('mongodb_export.json', 'r') as f:
    entries = json.load(f)

for entry in entries:
    try:
        # Add required 'id' field for Cosmos DB
        entry['id'] = str(entry.get('_id', entry.get('id')))
        container.create_item(entry)
    except exceptions.CosmosResourceExistsError:
        pass  # Item already exists
```

## 💰 Cost Optimization

1. **Use Free Tier**: Cosmos DB offers 1000 RU/s and 25GB free
2. **Scale Down**: Use B1 App Service plan for development
3. **Monitor Usage**: Set up Azure Cost Management alerts
4. **Auto-scaling**: Configure based on demand

## 🔒 Security Best Practices

1. **Key Vault**: Store connection strings in Azure Key Vault
2. **Managed Identity**: Use managed identity for service-to-service auth
3. **Network Security**: Configure VNet integration
4. **SSL/TLS**: Enable HTTPS only
5. **CORS**: Configure proper CORS policies

## 📊 Monitoring

1. **Application Insights**: Monitor app performance
2. **Cosmos DB Metrics**: Track RU consumption
3. **Alerts**: Set up alerts for failures
4. **Logs**: Configure structured logging

## 🚨 Troubleshooting

### Common Issues:

1. **CORS Errors**: Update React API base URL
2. **Connection Timeouts**: Check Cosmos DB firewall settings
3. **High RU Usage**: Optimize queries and indexing
4. **Build Failures**: Verify Node.js version compatibility

### Debug Commands:

```bash
# Check Cosmos DB connection
az cosmosdb database list --name chuuk-dictionary-db --resource-group your-rg

# View app logs
az webapp log tail --name chuuk-dictionary-api --resource-group your-rg

# Test API endpoints
curl https://chuuk-dictionary-api.azurewebsites.net/api/health
```

## 🎯 Next Steps

1. Set up CI/CD pipeline with GitHub Actions
2. Configure staging environment
3. Implement caching with Redis
4. Add CDN for static assets
5. Set up backup and disaster recovery