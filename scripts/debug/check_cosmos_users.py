#!/usr/bin/env python3
"""
Check what users are in Cosmos DB vs the file  
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("Checking Cosmos DB Users")
print("=" * 70)

try:
    from src.database.user_db import UserDB
    
    user_db = UserDB()
    
    if not user_db.is_connected():
        print("ℹ️  Cosmos DB is NOT connected")
        print("   App will use config/users.json (file-based auth)")
    else:
        print("✅ Cosmos DB IS connected")
        print("\nUsers in Cosmos DB:")
        print("-" * 70)
        
        users = user_db.get_all_users()
        
        if not users:
            print("   (No users found)")
        else:
            for i, user in enumerate(users, 1):
                print(f"\n{i}. {user.get('name', 'N/A')}")
                print(f"   Email: {user['email']}")
                print(f"   Access Code: {user['access_code']}")
                print(f"   Role: {user.get('role', 'user')}")
        
        # Compare with file
        print("\n" + "=" * 70)
        print("Comparing with config/users.json")
        print("=" * 70)
        
        import json
        with open(project_root / 'config' / 'users.json', 'r') as f:
            data = json.load(f)
            file_users = data.get('users', [])
        
        for file_user in file_users:
            email = file_user['email']
            file_code = file_user['access_code']
            
            # Find in Cosmos DB
            db_user = next((u for u in users if u['email'].lower() == email.lower()), None)
            
            if not db_user:
                print(f"\n⚠️  {email}")
                print(f"   NOT in Cosmos DB")
                print(f"   Run: python scripts/migrate_users_to_cosmos.py")
            else:
                db_code = db_user['access_code']
                if file_code == db_code:
                    print(f"\n✅ {email}")
                    print(f"   Access codes MATCH")
                else:
                    print(f"\n❌ {email}")
                    print(f"   Access codes DIFFER!")
                    print(f"   File: {file_code}")
                    print(f"   DB:   {db_code}")
                    print(f"   SOLUTION: Update Cosmos DB with: python scripts/migrate_users_to_cosmos.py")

except ImportError as e:
    print(f"❌ Cannot check Cosmos DB: {e}")
    print("   pymongo not installed")
except Exception as e:
    print(f"❌ Error: {e}")
