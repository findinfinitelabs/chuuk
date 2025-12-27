"""
Database abstraction layer for Azure Cosmos DB with MongoDB API.
Supports both connection string and managed identity authentication.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists (local development)
# In production (Azure), environment variables are set directly
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"📁 Loaded .env file from: {env_path}")
else:
    print(f"☁️ Using environment variables from Azure (no .env file)")

def get_database_client():
    """Get Cosmos DB client using MongoDB API"""
    return get_cosmos_client()

def _get_client_with_managed_identity(account_name: str):
    """Get Cosmos DB client using Azure Managed Identity.
    
    This is the most secure authentication method for Azure resources.
    The managed identity must have appropriate RBAC permissions on Cosmos DB.
    """
    try:
        from pymongo import MongoClient
        from azure.identity import DefaultAzureCredential
        
        print(f"🔐 Using Managed Identity for Cosmos DB authentication")
        
        # Get access token using managed identity
        credential = DefaultAzureCredential()
        # Cosmos DB MongoDB API uses the Cosmos DB resource scope
        token = credential.get_token("https://cosmos.azure.com/.default")
        
        # Build connection string with token
        # For Cosmos DB MongoDB API with AAD auth
        connection_string = (
            f"mongodb://{account_name}:{token.token}@{account_name}.mongo.cosmos.azure.com:10255/"
            f"?ssl=true&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@{account_name}@&retryWrites=false"
            f"&authMechanism=MONGODB-AWS"
        )
        
        print(f"✅ Connecting to Azure Cosmos DB with Managed Identity: {account_name}.mongo.cosmos.azure.com")
        return MongoClient(connection_string, serverSelectionTimeoutMS=30000)
        
    except ImportError as e:
        print(f"⚠️ azure-identity package required for managed identity. Install with: pip install azure-identity")
        raise
    except Exception as e:
        print(f"❌ Managed Identity authentication failed: {e}")
        raise

def get_cosmos_client():
    """Get Cosmos DB client using MongoDB API.
    
    Authentication order:
    1. Direct MongoDB connection string (COSMOS_MONGO_CONNECTION_STRING)
    2. Managed Identity (if USE_MANAGED_IDENTITY=true)
    3. Connection string with key (COSMOS_DB_URI + COSMOS_DB_KEY)
    4. Fallback to local MongoDB
    """
    try:
        from pymongo import MongoClient
        import urllib.parse
        
        # Check for direct MongoDB connection string first
        mongo_connection_string = os.getenv('COSMOS_MONGO_CONNECTION_STRING')
        if mongo_connection_string:
            print(f"✅ Using direct MongoDB connection string")
            return MongoClient(mongo_connection_string, serverSelectionTimeoutMS=30000)
        
        # Check if managed identity is enabled
        use_managed_identity = os.getenv('USE_MANAGED_IDENTITY', 'false').lower() == 'true'
        account_name = os.getenv('COSMOS_ACCOUNT_NAME', 'chuuk-dictionary-cosmos')
        
        if use_managed_identity:
            return _get_client_with_managed_identity(account_name)
        
        # Get Azure Cosmos DB details (connection string auth)
        endpoint = os.getenv('COSMOS_DB_URI', 'https://localhost:8081')
        key = os.getenv('COSMOS_DB_KEY')
        
        print(f"🔍 DB Connection Debug:")
        print(f"  - endpoint: {endpoint}")
        print(f"  - key exists: {bool(key)}")
        print(f"  - 'chuuk-dictionary-cosmos' in endpoint: {'chuuk-dictionary-cosmos' in endpoint}")
        print(f"  - 'cosmos.azure.com' in endpoint: {'cosmos.azure.com' in endpoint}")
        
        if key and ('chuuk-dictionary-cosmos' in endpoint or 'cosmos.azure.com' in endpoint):
            # Azure Cosmos DB MongoDB connection string
            # URL-encode the key to handle special characters
            encoded_key = urllib.parse.quote_plus(key)
            connection_string = f"mongodb://{account_name}:{encoded_key}@{account_name}.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@{account_name}@&retryWrites=false"
            print(f"✅ Connecting to Azure Cosmos DB: {account_name}.mongo.cosmos.azure.com")
            return MongoClient(connection_string, serverSelectionTimeoutMS=30000)
        else:
            # Fallback to local MongoDB
            print("❌ Connecting to local MongoDB (Cosmos DB credentials not found)")
            return MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
            
    except ImportError:
        raise ImportError("pymongo package required for MongoDB API. Install with: pip install pymongo")

def get_database_config():
    """Get Cosmos DB configuration"""
    return {
        'type': 'cosmos',
        'database_name': 'chuuk_dictionary',
        'container_name': 'dictionary_entries',
        'pages_container': 'dictionary_pages',
        'words_container': 'words',
        'phrases_container': 'phrases', 
        'paragraphs_container': 'paragraphs'
    }