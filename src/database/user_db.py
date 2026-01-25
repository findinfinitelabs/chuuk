"""
User Database Manager for Chuuk Dictionary
Handles user authentication and management using Azure Cosmos DB with MongoDB API
"""
import os
from typing import List, Dict, Optional
from datetime import datetime, timezone
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError


class UserDB:
    """Manages user accounts in Azure Cosmos DB"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern to reuse database connection"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize database connection"""
        if UserDB._initialized:
            return
            
        from .db_factory import get_database_client, get_database_config
        
        self.config = get_database_config()
        self.db_type = self.config['type']
        
        try:
            # Use Cosmos DB with MongoDB API
            self.client = get_database_client()
            self.db = self.client[self.config['database_name']]
            self.users_collection = self.db[self.config['users_container']]
            self._create_indexes()
            UserDB._initialized = True
            print("✅ UserDB connected to Azure Cosmos DB")
        except Exception as e:
            print(f"❌ UserDB connection failed: {e}")
            self.client = None
            self.users_collection = None
    
    def _create_indexes(self):
        """Create database indexes for efficient user lookups"""
        if self.users_collection is None:
            return
            
        try:
            # Unique index on email (case-insensitive queries will be done in code)
            self.users_collection.create_index([('email', ASCENDING)], unique=True)
            print("✅ UserDB indexes created")
        except Exception as e:
            # Index might already exist
            print(f"ℹ️ UserDB index creation: {e}")
    
    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self.users_collection is not None
    
    def get_all_users(self) -> List[Dict]:
        """Get all users from database"""
        if not self.is_connected():
            return []
        
        try:
            users = list(self.users_collection.find({}, {'_id': 0}))
            return users
        except Exception as e:
            print(f"❌ Failed to get users: {e}")
            return []
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get a user by email (case-insensitive)"""
        if not self.is_connected():
            return None
        
        try:
            # Case-insensitive search using regex
            user = self.users_collection.find_one(
                {'email': {'$regex': f'^{email}$', '$options': 'i'}},
                {'_id': 0}
            )
            return user
        except Exception as e:
            print(f"❌ Failed to get user {email}: {e}")
            return None
    
    def authenticate_user(self, email: str, access_code: str) -> Optional[Dict]:
        """Authenticate user by email and access code"""
        if not self.is_connected():
            return None
        
        try:
            user = self.users_collection.find_one(
                {
                    'email': {'$regex': f'^{email}$', '$options': 'i'},
                    'access_code': access_code
                },
                {'_id': 0}
            )
            return user
        except Exception as e:
            print(f"❌ Authentication failed for {email}: {e}")
            return None
    
    def create_user(self, user_data: Dict) -> bool:
        """Create a new user"""
        if not self.is_connected():
            return False
        
        try:
            # Ensure required fields
            if 'email' not in user_data or 'access_code' not in user_data:
                print("❌ User must have email and access_code")
                return False
            
            # Set defaults
            user_data.setdefault('role', 'user')
            user_data.setdefault('terms_accepted', False)
            user_data.setdefault('created_at', datetime.now(timezone.utc).isoformat())
            
            self.users_collection.insert_one(user_data)
            print(f"✅ Created user: {user_data['email']}")
            return True
        except DuplicateKeyError:
            print(f"❌ User already exists: {user_data.get('email')}")
            return False
        except Exception as e:
            print(f"❌ Failed to create user: {e}")
            return False
    
    def update_user(self, email: str, update_data: Dict) -> bool:
        """Update a user's data"""
        if not self.is_connected():
            return False
        
        try:
            result = self.users_collection.update_one(
                {'email': {'$regex': f'^{email}$', '$options': 'i'}},
                {'$set': update_data}
            )
            if result.modified_count > 0:
                print(f"✅ Updated user: {email}")
                return True
            else:
                print(f"ℹ️ No changes made for user: {email}")
                return False
        except Exception as e:
            print(f"❌ Failed to update user {email}: {e}")
            return False
    
    def update_terms_acceptance(self, email: str, terms_accepted_at: str) -> bool:
        """Update user's terms acceptance"""
        return self.update_user(email, {
            'terms_accepted': True,
            'terms_accepted_at': terms_accepted_at
        })
    
    def delete_user(self, email: str) -> bool:
        """Delete a user"""
        if not self.is_connected():
            return False
        
        try:
            result = self.users_collection.delete_one(
                {'email': {'$regex': f'^{email}$', '$options': 'i'}}
            )
            if result.deleted_count > 0:
                print(f"✅ Deleted user: {email}")
                return True
            else:
                print(f"ℹ️ User not found: {email}")
                return False
        except Exception as e:
            print(f"❌ Failed to delete user {email}: {e}")
            return False
    
    def count_users(self) -> int:
        """Count total users"""
        if not self.is_connected():
            return 0
        
        try:
            return self.users_collection.count_documents({})
        except Exception as e:
            print(f"❌ Failed to count users: {e}")
            return 0


# Global instance for easy access
_user_db = None

def get_user_db() -> UserDB:
    """Get the global UserDB instance"""
    global _user_db
    if _user_db is None:
        _user_db = UserDB()
    return _user_db
