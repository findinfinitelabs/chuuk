"""
Database abstraction layer for Azure Cosmos DB with MongoDB API
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

def get_cosmos_client():
    """Get Cosmos DB client using MongoDB API"""
    try:
        from pymongo import MongoClient
        
        # Get Azure Cosmos DB details
        endpoint = os.getenv('COSMOS_DB_URI', 'https://localhost:8081')
        key = os.getenv('COSMOS_DB_KEY')
        
        print(f"🔍 DB Connection Debug:")
        print(f"  - endpoint: {endpoint}")
        print(f"  - key exists: {bool(key)}")
        print(f"  - 'chuuk-dictionary-cosmos' in endpoint: {'chuuk-dictionary-cosmos' in endpoint}")
        print(f"  - 'cosmos.azure.com' in endpoint: {'cosmos.azure.com' in endpoint}")
        
        if key and ('chuuk-dictionary-cosmos' in endpoint or 'cosmos.azure.com' in endpoint):
            # Azure Cosmos DB MongoDB connection string
            account_name = 'chuuk-dictionary-cosmos'
            connection_string = f"mongodb://{account_name}:{key}@{account_name}.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@{account_name}@&retryWrites=false"
            print(f"✅ Connecting to Azure Cosmos DB: {account_name}.mongo.cosmos.azure.com")
            return MongoClient(connection_string, serverSelectionTimeoutMS=10000)
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