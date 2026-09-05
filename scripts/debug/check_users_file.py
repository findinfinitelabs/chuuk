#!/usr/bin/env python3
"""
Check what users the app can see vs what's in the file
"""
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Check the file directly
print("=" * 70)
print("Users in config/users.json")
print("=" * 70)

users_file = project_root / 'config' / 'users.json'
with open(users_file, 'r') as f:
    file_content = f.read()
    print(file_content)

print("\n" + "=" * 70)
print("Parsed JSON")
print("=" * 70)

data = json.loads(file_content)
users = data.get('users', [])

for i, user in enumerate(users, 1):
    print(f"\nUser {i}:")
    print(f"  email: {repr(user.get('email'))}")
    print(f"  access_code: {repr(user.get('access_code'))}")
    print(f"  name: {repr(user.get('name'))}")
    print(f"  role: {repr(user.get('role'))}")

# Try to test authentication through the app's load_users function
print("\n" + "=" * 70)
print("Testing app.py load_users() function")
print("=" * 70)

try:
    # Import without running the app
    import os
    os.environ['FLASK_ENV'] = 'development'  # Prevent any startup issues
    
    # We can't import app.py directly because it starts the server
    # Instead, let's just verify the file is readable
    print(f"✅ File exists: {users_file.exists()}")
    print(f"✅ File is readable: {users_file.is_file()}")
    print(f"✅ File size: {users_file.stat().st_size} bytes")
    print(f"✅ Number of users in file: {len(users)}")
    
except Exception as e:
    print(f"❌ Error: {e}")
