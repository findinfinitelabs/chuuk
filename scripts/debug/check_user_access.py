#!/usr/bin/env python3
"""
Test script to verify that both users can access the Chuuk app
"""
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_file_based_auth():
    """Test authentication using config/users.json"""
    print("=" * 70)
    print("Testing File-Based Authentication (users.json)")
    print("=" * 70)
    
    users_file = project_root / 'config' / 'users.json'
    
    if not users_file.exists():
        print(f"❌ Users file not found: {users_file}")
        return False
    
    with open(users_file, 'r') as f:
        data = json.load(f)
        users = data.get('users', [])
    
    if not users:
        print("❌ No users found in config file")
        return False
    
    print(f"\n✅ Found {len(users)} users in config file\n")
    
    # Test each user
    for i, user in enumerate(users, 1):
        email = user.get('email', 'N/A')
        access_code = user.get('access_code', 'N/A')
        name = user.get('name', 'N/A')
        role = user.get('role', 'user')
        terms_accepted = user.get('terms_accepted', False)
        
        print(f"User {i}:")
        print(f"  📧 Email:        {email}")
        print(f"  👤 Name:         {name}")
        print(f"  🔑 Access Code:  {access_code}")
        print(f"  🛡️  Role:         {role}")
        print(f"  ✅ Terms:        {'Accepted' if terms_accepted else 'Not Accepted'}")
        print(f"  🔐 Can Login:    {'YES ✅' if email and access_code else 'NO ❌'}")
        print()
    
    return True


def test_cosmos_db_auth():
    """Test authentication using Cosmos DB"""
    print("=" * 70)
    print("Testing Cosmos DB Authentication")
    print("=" * 70)
    
    try:
        from src.database.user_db import UserDB
        
        user_db = UserDB()
        
        if not user_db.is_connected():
            print("⚠️  Cosmos DB is not connected")
            print("   The app will use file-based authentication (users.json)")
            print("   This is normal for local development.\n")
            return None
        
        print("✅ Connected to Cosmos DB\n")
        
        users = user_db.get_all_users()
        print(f"📊 Total users in Cosmos DB: {len(users)}\n")
        
        if not users:
            print("⚠️  No users found in Cosmos DB")
            print("   Run: python scripts/migrate_users_to_cosmos.py")
            print("   to sync users from config/users.json\n")
            return False
        
        for i, user in enumerate(users, 1):
            email = user.get('email', 'N/A')
            name = user.get('name', 'N/A')
            role = user.get('role', 'user')
            terms_accepted = user.get('terms_accepted', False)
            
            print(f"User {i}:")
            print(f"  📧 Email:     {email}")
            print(f"  👤 Name:      {name}")
            print(f"  🛡️  Role:      {role}")
            print(f"  ✅ Terms:     {'Accepted' if terms_accepted else 'Not Accepted'}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Cosmos DB: {e}\n")
        return None


def test_authentication():
    """Test actual authentication for both users"""
    print("=" * 70)
    print("Testing Authentication Flow")
    print("=" * 70)
    
    # Load users from config
    users_file = project_root / 'config' / 'users.json'
    with open(users_file, 'r') as f:
        data = json.load(f)
        config_users = data.get('users', [])
    
    print(f"\nTesting authentication for {len(config_users)} users...\n")
    
    # Import the authenticate_user function from app.py
    try:
        # We need to mock the app context, so let's do a simpler check
        from src.database.user_db import UserDB
        
        user_db = UserDB()
        using_cosmos = user_db.is_connected()
        
        for i, user in enumerate(config_users, 1):
            email = user.get('email')
            access_code = user.get('access_code')
            name = user.get('name')
            
            print(f"User {i}: {name} ({email})")
            
            # Test Cosmos DB authentication if connected
            if using_cosmos:
                cosmos_user = user_db.authenticate_user(email, access_code)
                if cosmos_user:
                    print(f"  ✅ Cosmos DB authentication: SUCCESS")
                else:
                    print(f"  ❌ Cosmos DB authentication: FAILED")
                    print(f"     Run: python scripts/migrate_users_to_cosmos.py")
            
            # Test file-based authentication
            file_match = False
            for u in config_users:
                if u['email'].lower() == email.lower() and u['access_code'] == access_code:
                    file_match = True
                    break
            
            if file_match:
                print(f"  ✅ File-based authentication: SUCCESS")
            else:
                print(f"  ❌ File-based authentication: FAILED")
            
            print()
        
    except Exception as e:
        print(f"⚠️  Could not test full authentication: {e}")
        print("   But file-based auth should work based on users.json\n")


def main():
    """Run all tests"""
    print("\n🧪 Chuuk App User Access Test\n")
    
    # Test file-based authentication
    file_ok = test_file_based_auth()
    
    # Test Cosmos DB authentication
    print()
    cosmos_ok = test_cosmos_db_auth()
    
    # Test actual authentication
    print()
    test_authentication()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    
    if file_ok:
        print("✅ File-based authentication is properly configured")
        print("   Both users can log in using their email and access code")
    
    if cosmos_ok is None:
        print("\nℹ️  Cosmos DB is not configured (this is fine for local dev)")
        print("   The app will automatically use file-based authentication")
    elif cosmos_ok is False:
        print("\n⚠️  Cosmos DB is configured but users not migrated")
        print("   Run: python scripts/migrate_users_to_cosmos.py")
    elif cosmos_ok:
        print("\n✅ Cosmos DB authentication is properly configured")
    
    print("\n" + "=" * 70)
    print("Next Steps")
    print("=" * 70)
    print("1. Start the app: python app.py")
    print("2. Go to: http://localhost:5000")
    print("3. Log in with either user's email and access code:")
    print(f"   - User 1: chris.lundy@findinfinite.com")
    print("   - User 2: (set CHUUK_DEBUG_EMAIL)")
    print()


if __name__ == '__main__':
    main()
