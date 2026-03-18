#!/usr/bin/env python3
"""
Migrate users from config/users.json to Azure Cosmos DB users collection.

This script reads users from the local config file and creates them in Cosmos DB.
Run this script once to seed your initial users into the database.

Usage:
    python scripts/migrate_users_to_cosmos.py

The script will:
1. Connect to Cosmos DB using environment variables
2. Read users from config/users.json
3. Create each user in the users collection (skipping duplicates)
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.user_db import UserDB


def migrate_users():
    """Migrate users from config file to Cosmos DB"""
    print("🚀 Starting user migration to Cosmos DB...")

    # Initialize UserDB
    user_db = UserDB()

    if not user_db.is_connected():
        print("❌ Failed to connect to Cosmos DB. Check your environment variables:")
        print("   - COSMOS_MONGO_CONNECTION_STRING (recommended)")
        print("   - Or: COSMOS_DB_URI + COSMOS_DB_KEY")
        return False

    # Read users from config file
    users_file = project_root / "config" / "users.json"
    if not users_file.exists():
        print(f"❌ Users file not found: {users_file}")
        return False

    with open(users_file) as f:
        data = json.load(f)
        users = data.get("users", [])

    if not users:
        print("ℹ️ No users found in config file")
        return True

    print(f"📋 Found {len(users)} users to migrate")

    # Migrate each user
    success_count = 0
    skip_count = 0
    fail_count = 0

    for user in users:
        email = user.get("email", "unknown")

        # Check if user already exists
        existing = user_db.get_user_by_email(email)
        if existing:
            print(f"⏭️  Skipping {email} - already exists in Cosmos DB")
            skip_count += 1
            continue

        # Create user in Cosmos DB
        if user_db.create_user(user.copy()):
            success_count += 1
        else:
            fail_count += 1

    print("\n✅ Migration complete!")
    print(f"   Created: {success_count}")
    print(f"   Skipped: {skip_count}")
    print(f"   Failed:  {fail_count}")
    print(f"   Total users in Cosmos DB: {user_db.count_users()}")

    return fail_count == 0


def verify_users():
    """Verify users in Cosmos DB"""
    print("\n🔍 Verifying users in Cosmos DB...")

    user_db = UserDB()

    if not user_db.is_connected():
        print("❌ Not connected to Cosmos DB")
        return

    users = user_db.get_all_users()
    print(f"📊 Total users: {len(users)}")

    for user in users:
        role = user.get("role", "user")
        terms = "✅" if user.get("terms_accepted") else "❌"
        print(f"   • {user.get('email')} ({role}) - Terms accepted: {terms}")


if __name__ == "__main__":
    if migrate_users():
        verify_users()
        print("\n🎉 Users are now stored in Cosmos DB!")
    else:
        print("\n⚠️ Migration had issues. Please check the errors above.")
        sys.exit(1)
