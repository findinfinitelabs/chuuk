#!/usr/bin/env python3
"""
Database cleanup script - clears all data and uploads
"""
import os
import shutil
import sys
from pymongo import MongoClient

def clear_database():
    """Clear all MongoDB collections"""
    try:
        client = MongoClient('mongodb://localhost:27017/')
        db = client['chuuk_dictionary']
        
        # Drop all collections
        collections = db.list_collection_names()
        for collection_name in collections:
            db[collection_name].drop()
            print(f"✓ Cleared collection: {collection_name}")
        
        client.close()
        print("✅ Database cleared successfully")
        return True
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        return False

def clear_uploads():
    """Remove all uploaded files"""
    uploads_dir = 'uploads'
    if os.path.exists(uploads_dir):
        try:
            shutil.rmtree(uploads_dir)
            os.makedirs(uploads_dir, exist_ok=True)
            print("✅ Uploads directory cleared and recreated")
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
    
    # Clear uploads
    uploads_success = clear_uploads()
    
    # Summary
    print("\n📊 Cleanup Summary:")
    print(f"Database: {'✅ Cleared' if db_success else '❌ Failed'}")
    print(f"Uploads: {'✅ Cleared' if uploads_success else '❌ Failed'}")
    
    if db_success and uploads_success:
        print("\n🎉 Cleanup completed successfully!")
        print("You can now start fresh with new uploads.")
    else:
        print("\n⚠️ Some cleanup operations failed. Check the errors above.")

if __name__ == "__main__":
    main()