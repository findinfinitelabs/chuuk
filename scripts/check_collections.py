"""
Check all Cosmos DB collections - count documents and analyze usage
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_factory import get_database_client, get_database_config

def check_collections():
    """Check all collections and their document counts"""
    
    # Connect to database
    config = get_database_config()
    client = get_database_client()
    db = client[config['database_name']]
    
    print("📊 Cosmos DB Collections Analysis")
    print("=" * 60)
    
    collections = {
        'dictionary_entries': 'Main dictionary entries (from OCR)',
        'dictionary_pages': 'OCR processed pages',
        'words': 'Individual words collection',
        'phrases': 'Phrase pairs collection',
        'paragraphs': 'Paragraph pairs collection'
    }
    
    total_docs = 0
    
    for collection_name, description in collections.items():
        try:
            collection = db[collection_name]
            count = collection.count_documents({})
            total_docs += count
            
            status = "✅ ACTIVE" if count > 0 else "⚠️  EMPTY"
            print(f"\n{status} {collection_name}")
            print(f"  Description: {description}")
            print(f"  Documents: {count:,}")
            
            # Sample a document if available
            if count > 0:
                sample = collection.find_one()
                if sample:
                    print(f"  Fields: {', '.join(sample.keys())}")
                    
                    # Check for date to see when last updated
                    if 'date_added' in sample:
                        print(f"  Sample date: {sample['date_added']}")
                    elif 'created_date' in sample:
                        print(f"  Sample date: {sample['created_date']}")
                    elif 'processed_date' in sample:
                        print(f"  Sample date: {sample['processed_date']}")
                        
        except Exception as e:
            print(f"\n❌ ERROR {collection_name}")
            print(f"  Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"Total documents across all collections: {total_docs:,}")
    
    client.close()

if __name__ == '__main__':
    try:
        check_collections()
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
