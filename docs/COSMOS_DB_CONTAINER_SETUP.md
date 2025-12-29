# Azure Cosmos DB + Container Apps Integration Guide

## Overview
This guide explains how a containerized Python/Flask application communicates with Azure Cosmos DB using the MongoDB API. This setup is production-ready and follows Azure best practices.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Azure Container Apps                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Docker Container (Python Flask App)                   │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  App Code (Python)                               │  │  │
│  │  │  - Uses pymongo library                          │  │  │
│  │  │  - Reads env vars for connection                 │  │  │
│  │  │  - COSMOS_DB_URI, COSMOS_DB_KEY                  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ HTTPS (Port 10255)
                          │ MongoDB Wire Protocol
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Azure Cosmos DB (MongoDB API)                   │
│  - Account: your-account.mongo.cosmos.azure.com             │
│  - Database: your_database                                   │
│  - Collections: your_collections                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Cosmos DB Configuration

**MongoDB API Endpoint:**
- Format: `your-account.mongo.cosmos.azure.com:10255`
- Protocol: MongoDB Wire Protocol over SSL
- Port: 10255 (SSL required)

**Connection String Format:**
```
mongodb://ACCOUNT_NAME:PRIMARY_KEY@ACCOUNT_NAME.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@ACCOUNT_NAME@&retryWrites=false
```

### 2. Python Connection Code

**File: `src/database/db_factory.py`**

```python
import os
import urllib.parse
from pymongo import MongoClient

def get_cosmos_client():
    """Connect to Cosmos DB using MongoDB API"""
    
    # Get credentials from environment variables
    account_name = os.getenv('COSMOS_ACCOUNT_NAME', 'your-cosmos-account')
    endpoint = os.getenv('COSMOS_DB_URI')
    key = os.getenv('COSMOS_DB_KEY')
    
    # URL-encode the key to handle special characters
    encoded_key = urllib.parse.quote_plus(key)
    
    # Build connection string
    connection_string = (
        f"mongodb://{account_name}:{encoded_key}@"
        f"{account_name}.mongo.cosmos.azure.com:10255/"
        f"?ssl=true&replicaSet=globaldb&maxIdleTimeMS=120000"
        f"&appName=@{account_name}@&retryWrites=false"
    )
    
    # Create client with timeout
    return MongoClient(connection_string, serverSelectionTimeoutMS=30000)

# Usage in your app
client = get_cosmos_client()
db = client['your_database']
collection = db['your_collection']
```

### 3. Environment Variables

**Required Environment Variables:**

```bash
# Database type
DB_TYPE=cosmos

# Cosmos DB credentials
COSMOS_DB_URI=https://your-account.documents.azure.com:443/
COSMOS_DB_KEY=your-primary-or-secondary-key-here
COSMOS_ACCOUNT_NAME=your-cosmos-account

# Optional: For managed identity (more secure)
USE_MANAGED_IDENTITY=true  # If using Azure AD
```

---

## Step-by-Step Setup Instructions

### Step 1: Create Cosmos DB Account

```bash
# Set variables
RESOURCE_GROUP="rg-your-project"
LOCATION="eastus2"
COSMOS_ACCOUNT="your-cosmos-account"

# Create Cosmos DB account with MongoDB API
az cosmosdb create \
    --name $COSMOS_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --kind MongoDB \
    --server-version 6.0 \
    --default-consistency-level Session \
    --locations regionName=$LOCATION failoverPriority=0 isZoneRedundant=False

# Create database
az cosmosdb mongodb database create \
    --account-name $COSMOS_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --name your_database

# Create collection
az cosmosdb mongodb collection create \
    --account-name $COSMOS_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --database-name your_database \
    --name your_collection \
    --throughput 400
```

### Step 2: Get Connection Credentials

```bash
# Get the primary key
COSMOS_DB_KEY=$(az cosmosdb keys list \
    --name $COSMOS_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --type keys \
    --query "primaryMasterKey" \
    --output tsv)

# Get the URI
COSMOS_DB_URI="https://${COSMOS_ACCOUNT}.documents.azure.com:443/"

echo "COSMOS_DB_URI=$COSMOS_DB_URI"
echo "COSMOS_DB_KEY=$COSMOS_DB_KEY"
```

### Step 3: Create Dockerfile

```dockerfile
# Multi-stage build
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "600", "app:app"]
```

**Required in `requirements.txt`:**
```
pymongo>=4.6.0
flask>=3.0.0
gunicorn>=21.2.0
```

### Step 4: Build and Push Container Image

```bash
CONTAINER_REGISTRY="yourregistry"
IMAGE_NAME="your-app"
IMAGE_TAG="latest"

# Create Azure Container Registry
az acr create \
    --name $CONTAINER_REGISTRY \
    --resource-group $RESOURCE_GROUP \
    --sku Basic \
    --admin-enabled true

# Build and push image
az acr build \
    --registry $CONTAINER_REGISTRY \
    --image $IMAGE_NAME:$IMAGE_TAG \
    --file Dockerfile \
    .
```

### Step 5: Deploy to Container Apps

```bash
CONTAINER_APP_ENV="your-app-env"
CONTAINER_APP_NAME="your-app"

# Create Container Apps environment
az containerapp env create \
    --name $CONTAINER_APP_ENV \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION

# Get ACR credentials
ACR_USERNAME=$(az acr credential show \
    --name $CONTAINER_REGISTRY \
    --query username \
    --output tsv)

ACR_PASSWORD=$(az acr credential show \
    --name $CONTAINER_REGISTRY \
    --query passwords[0].value \
    --output tsv)

ACR_LOGIN_SERVER=$(az acr show \
    --name $CONTAINER_REGISTRY \
    --query loginServer \
    --output tsv)

# Deploy container app with Cosmos DB credentials
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
        "COSMOS_ACCOUNT_NAME=$COSMOS_ACCOUNT"
```

---

## How Communication Works

### 1. **Container Startup**
- Container starts in Azure Container Apps
- Python app reads environment variables (`COSMOS_DB_URI`, `COSMOS_DB_KEY`)
- Application code loads `db_factory.py`

### 2. **Connection Initialization**
```python
# App reads environment variables
endpoint = os.getenv('COSMOS_DB_URI')
key = os.getenv('COSMOS_DB_KEY')

# Constructs MongoDB connection string
connection_string = f"mongodb://{account}:{encoded_key}@{account}.mongo.cosmos.azure.com:10255/..."

# Creates MongoClient
client = MongoClient(connection_string)
```

### 3. **Network Communication**
- **Protocol**: MongoDB Wire Protocol (BSON over TCP)
- **Transport**: HTTPS/SSL (Port 10255)
- **Direction**: Outbound from Container Apps to Cosmos DB
- **Authentication**: Primary/Secondary Key in connection string
- **No VNet Required**: Public endpoint with SSL/TLS encryption

### 4. **Data Operations**
```python
# App uses standard MongoDB operations
collection.find_one({'_id': doc_id})
collection.insert_one({'field': 'value'})
collection.update_one({'_id': doc_id}, {'$set': {...}})
```

### 5. **Connection Pooling**
- `MongoClient` maintains connection pool
- Connections are reused across requests
- `maxIdleTimeMS=120000` keeps connections alive

---

## Security Best Practices

### Option 1: Connection String (Current Setup)
**Pros:**
- Simple setup
- Works immediately
- Good for development

**Cons:**
- Keys stored as environment variables
- Need to rotate keys manually

**Implementation:**
```bash
az containerapp create \
    --env-vars \
        "COSMOS_DB_URI=$COSMOS_DB_URI" \
        "COSMOS_DB_KEY=$COSMOS_DB_KEY"
```

### Option 2: Managed Identity (Recommended for Production)
**Pros:**
- No secrets in environment variables
- Azure handles authentication
- Automatic key rotation

**Implementation:**

1. **Enable managed identity on Container App:**
```bash
az containerapp identity assign \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --system-assigned
```

2. **Get managed identity principal ID:**
```bash
PRINCIPAL_ID=$(az containerapp identity show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query principalId \
    --output tsv)
```

3. **Grant Cosmos DB access:**
```bash
COSMOS_DB_ID=$(az cosmosdb show \
    --name $COSMOS_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --query id \
    --output tsv)

az role assignment create \
    --assignee $PRINCIPAL_ID \
    --role "Cosmos DB Account Reader Role" \
    --scope $COSMOS_DB_ID
```

4. **Update Python code:**
```python
from azure.identity import DefaultAzureCredential

def get_cosmos_client_with_managed_identity():
    credential = DefaultAzureCredential()
    token = credential.get_token("https://cosmos.azure.com/.default")
    
    connection_string = (
        f"mongodb://{account_name}:{token.token}@"
        f"{account_name}.mongo.cosmos.azure.com:10255/"
        f"?ssl=true&authMechanism=MONGODB-AWS"
    )
    return MongoClient(connection_string)
```

5. **Update container app:**
```bash
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --set-env-vars \
        "USE_MANAGED_IDENTITY=true" \
        "COSMOS_ACCOUNT_NAME=$COSMOS_ACCOUNT"
```

---

## Network Configuration

### Public Endpoint (Default)
- **No VNet required**
- Cosmos DB has public endpoint: `*.mongo.cosmos.azure.com:10255`
- Container Apps can reach it over internet
- Traffic encrypted with SSL/TLS
- IP firewall can restrict access

### Private Endpoint (Optional for High Security)
1. **Create VNet:**
```bash
az network vnet create \
    --name your-vnet \
    --resource-group $RESOURCE_GROUP \
    --address-prefix 10.0.0.0/16
```

2. **Create subnet for Cosmos DB:**
```bash
az network vnet subnet create \
    --name cosmos-subnet \
    --vnet-name your-vnet \
    --resource-group $RESOURCE_GROUP \
    --address-prefixes 10.0.1.0/24
```

3. **Create private endpoint:**
```bash
az network private-endpoint create \
    --name cosmos-private-endpoint \
    --resource-group $RESOURCE_GROUP \
    --vnet-name your-vnet \
    --subnet cosmos-subnet \
    --private-connection-resource-id $COSMOS_DB_ID \
    --group-id MongoDB \
    --connection-name cosmos-connection
```

4. **Update Container Apps to use VNet:**
```bash
az containerapp env create \
    --name $CONTAINER_APP_ENV \
    --resource-group $RESOURCE_GROUP \
    --infrastructure-subnet-resource-id $SUBNET_ID
```

---

## Troubleshooting

### Common Issues

**1. Connection Timeout**
```
Error: MongoServerSelectionTimeoutError
```
**Solution:**
- Check if `COSMOS_DB_URI` and `COSMOS_DB_KEY` are set correctly
- Verify Cosmos DB firewall allows Container Apps IP
- Increase `serverSelectionTimeoutMS` to 30000

**2. Authentication Failed**
```
Error: Authentication failed
```
**Solution:**
- URL-encode the key: `urllib.parse.quote_plus(key)`
- Verify key hasn't been regenerated
- Check key is primary or secondary master key (not read-only)

**3. SSL/TLS Error**
```
Error: SSL handshake failed
```
**Solution:**
- Ensure connection string includes `?ssl=true`
- Update pymongo: `pip install --upgrade pymongo`

**4. Rate Limiting (429 errors)**
```
Error: Request rate is large (429)
```
**Solution:**
- Increase RU/s on collection
- Implement retry logic with exponential backoff
- Optimize queries to use indexes

### Debugging Commands

**Test connection from container:**
```bash
# Get into running container
az containerapp exec \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --command /bin/bash

# Inside container, test connection
python3 << EOF
from pymongo import MongoClient
import os
uri = os.getenv('COSMOS_DB_URI')
key = os.getenv('COSMOS_DB_KEY')
account = os.getenv('COSMOS_ACCOUNT_NAME')
import urllib.parse
encoded_key = urllib.parse.quote_plus(key)
conn_str = f"mongodb://{account}:{encoded_key}@{account}.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb"
client = MongoClient(conn_str, serverSelectionTimeoutMS=10000)
print("Databases:", client.list_database_names())
EOF
```

**View container logs:**
```bash
az containerapp logs show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --follow
```

**Check environment variables:**
```bash
az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "properties.template.containers[0].env"
```

---

## Performance Optimization

### 1. Connection Pooling
```python
# Create client once, reuse across requests
client = MongoClient(
    connection_string,
    maxPoolSize=50,  # Max connections
    minPoolSize=10,  # Keep-alive connections
    maxIdleTimeMS=120000
)
```

### 2. Index Creation
```python
# Create indexes for better performance
collection.create_index([("field", 1)])
collection.create_index([("text_field", "text")])  # Note: text indexes not supported on Cosmos DB
```

### 3. Batch Operations
```python
# Use bulk operations for multiple writes
from pymongo import InsertOne, UpdateOne
operations = [
    InsertOne({"doc": 1}),
    UpdateOne({"doc": 2}, {"$set": {"field": "value"}})
]
collection.bulk_write(operations)
```

### 4. Request Unit (RU) Optimization
- Monitor RU consumption in Azure Portal
- Use queries with indexed fields
- Limit result sets with `.limit()`
- Use projection to return only needed fields

---

## Cost Management

**Cosmos DB Pricing Factors:**
1. **Request Units (RU/s)**: Provisioned throughput
2. **Storage**: Data + indexes
3. **Backup**: Continuous backup optional

**Container Apps Pricing:**
1. **vCPU**: Per second usage
2. **Memory**: Per GB-second
3. **HTTP Requests**: Per million requests

**Cost-Saving Tips:**
- Use autoscaling RU/s (min 400, max based on load)
- Scale Container Apps to zero when idle (`--min-replicas 0`)
- Use shared throughput at database level
- Implement connection pooling to reduce RU consumption

---

## Complete Deployment Script

See `deploy-container-app.sh` for a complete automated deployment that:
1. Creates/updates Container Registry
2. Builds Docker image
3. Pushes to registry
4. Fetches Cosmos DB credentials
5. Deploys Container App with all environment variables
6. Configures ingress and scaling

---

## Additional Resources

- [Azure Cosmos DB MongoDB API Documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/introduction)
- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [PyMongo Documentation](https://pymongo.readthedocs.io/)
- [Cosmos DB Best Practices](https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/best-practices)

---

## Quick Reference

**Essential Environment Variables:**
```bash
DB_TYPE=cosmos
COSMOS_DB_URI=https://account.documents.azure.com:443/
COSMOS_DB_KEY=your-key-here
COSMOS_ACCOUNT_NAME=account-name
```

**Connection String Template:**
```
mongodb://ACCOUNT:KEY@ACCOUNT.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@ACCOUNT@&retryWrites=false
```

**Common Commands:**
```bash
# Deploy
./deploy-container-app.sh

# View logs
az containerapp logs show --name APP --resource-group RG --follow

# Update env vars
az containerapp update --name APP --resource-group RG --set-env-vars "KEY=VALUE"

# Scale
az containerapp update --name APP --resource-group RG --min-replicas 1 --max-replicas 5
```
