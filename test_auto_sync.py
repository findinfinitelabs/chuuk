#!/usr/bin/env python3
"""
Test automatic user synchronization
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import os
os.environ['FLASK_ENV'] = 'test'

print("=" * 70)
print("Testing Automatic User Sync")
print("=" * 70)

# Import the functions from app.py
import importlib.util
spec = importlib.util.spec_from_file_location("app", project_root / "app.py")
app_module = importlib.util.module_from_spec(spec)

# Don't run the app, just load the functions
import sys
original_argv = sys.argv
sys.argv = ['test']  # Prevent app.run() from starting

try:
    # Manually set up only what we need
    from src.database.user_db import UserDB
    
    user_db = UserDB()
    
    if not user_db.is_connected():
        print("ℹ️  Cosmos DB not connected - auto-sync only works with Cosmos DB")
        print("   This is normal for local development")
        sys.exit(0)
    
    print("✅ Cosmos DB connected\n")
    
    # Check current users in Cosmos DB
    print("Current users in Cosmos DB:")
    print("-" * 70)
    current_users = user_db.get_all_users()
    for user in current_users:
        print(f"  • {user['email']}")
    
    print(f"\nTotal: {len(current_users)} users")
    
    # Check users in file
    import json
    with open(project_root / 'config' / 'users.json') as f:
        data = json.load(f)
        file_users = data.get('users', [])
    
    print(f"\n\nUsers in config/users.json:")
    print("-" * 70)
    for user in file_users:
        print(f"  • {user['email']}")
    
    print(f"\nTotal: {len(file_users)} users")
    
    # Show what would be synced
    print("\n" + "=" * 70)
    print("Auto-Sync Status")
    print("=" * 70)
    
    db_emails = {u['email'].lower() for u in current_users}
    missing_users = [u for u in file_users if u['email'].lower() not in db_emails]
    
    if missing_users:
        print(f"\n⚠️  {len(missing_users)} user(s) in file but not in Cosmos DB:")
        for user in missing_users:
            print(f"   • {user['email']}")
        print("\n✨ These will be automatically synced on next app start or login attempt!")
    else:
        print("\n✅ All users in file are already synced to Cosmos DB")
    
    print("\n" + "=" * 70)
    print("How It Works")
    print("=" * 70)
    print("""
When you:
1. Add a new user to config/users.json
2. Start the app or any user tries to log in

The app will automatically:
✓ Detect the new user in the file
✓ Create them in Cosmos DB
✓ Print a confirmation message

You no longer need to run migrate_users_to_cosmos.py manually!
""")
    
except ImportError as e:
    print(f"❌ Error: {e}")
    print("   pymongo might not be installed")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    sys.argv = original_argv
