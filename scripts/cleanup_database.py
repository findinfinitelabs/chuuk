#!/usr/bin/env python3
"""
Database cleanup script - clears all data and uploads
"""
import os
import shutil
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.dictionary_db import DictionaryDB

def clear_database():
    """Clear all CosmosDB collections"""
    try:
        import time
        db = DictionaryDB()
        
        if not db.client:
            print("❌ Database connection failed")
            return False
        
        # Clear all collections
        collections = [
            ('dictionary_entries', db.dictionary_collection),
            ('dictionary_pages', db.pages_collection),
            ('words', db.words_collection),
            ('phrases', db.phrases_collection),
            ('paragraphs', db.paragraphs_collection)
        ]
        
        total_deleted = 0
        for name, collection in collections:
            count = collection.count_documents({})
            if count > 0:
                print(f"Clearing {name}: {count} documents...")
                
                # Delete in batches to avoid rate limiting
                batch_size = 100
                deleted = 0
                while True:
                    # Get a batch of IDs
                    docs = list(collection.find({}, {'_id': 1}).limit(batch_size))
                    if not docs:
                        break
                    
                    ids = [doc['_id'] for doc in docs]
                    try:
                        result = collection.delete_many({'_id': {'$in': ids}})
                        deleted += result.deleted_count
                        print(f"  Progress: {deleted}/{count}", end='\r')
                        
                        # Small delay to avoid rate limiting
                        time.sleep(0.1)
                    except Exception as e:
                        if 'RetryAfterMs' in str(e) or '16500' in str(e):
                            print(f"\n  Rate limited, waiting 2 seconds...")
                            time.sleep(2)
                            continue
                        else:
                            raise
                
                print(f"\n✓ Cleared {name}: {deleted} documents")
                total_deleted += deleted
            else:
                print(f"ℹ️ {name}: already empty")
        
        print(f"✅ Database cleared successfully ({total_deleted} total documents deleted)")
        return True
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        import traceback
        traceback.print_exc()
        return False

def clear_publications():
    """Clear publications metadata"""
    try:
        publications_file = 'uploads/publications.json'
        if os.path.exists(publications_file):
            # Create empty publications file
            with open(publications_file, 'w') as f:
                json.dump({}, f, indent=2)
            print("✅ Publications metadata cleared")
        else:
            # Create the file if it doesn't exist
            os.makedirs('uploads', exist_ok=True)
            with open(publications_file, 'w') as f:
                json.dump({}, f, indent=2)
            print("✅ Publications metadata file created (empty)")
        return True
    except Exception as e:
        print(f"❌ Error clearing publications: {e}")
        return False

def clear_uploads():
    """Remove all uploaded files"""
    uploads_dir = 'uploads'
    if os.path.exists(uploads_dir):
        try:
            # Keep the publications.json file but clear everything else
            for item in os.listdir(uploads_dir):
                item_path = os.path.join(uploads_dir, item)
                if item != 'publications.json':
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
            print("✅ Uploads directory cleared (preserving publications.json)")
            return True
        except Exception as e:
            print(f"❌ Error clearing uploads: {e}")
            return False
    else:
        print("ℹ️ Uploads directory doesn't exist")
        return True

def main():
    print("🧹 Chuuk Dictionary Database Cleanup")
    print("=" * 40)
    
    # Confirm action
    response = input("This will delete ALL database entries and uploaded files. Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cleanup cancelled.")
        return
    
    print("\n🗑️ Starting cleanup...")
    
    # Clear database
    db_success = clear_database()
    
    # Clear publications
    pub_success = clear_publications()
    
    # Clear uploads
    uploads_success = clear_uploads()
    
    # Summary
    print("\n📊 Cleanup Summary:")
    print(f"Database: {'✅ Cleared' if db_success else '❌ Failed'}")
    print(f"Publications: {'✅ Cleared' if pub_success else '❌ Failed'}")
    print(f"Uploads: {'✅ Cleared' if uploads_success else '❌ Failed'}")
    
    if db_success and pub_success and uploads_success:
        print("\n🎉 Cleanup completed successfully!")
        print("You can now start fresh with new uploads.")
    else:
        print("\n⚠️ Some cleanup operations failed. Check the errors above.")

if __name__ == "__main__":
    main()