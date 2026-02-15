#!/usr/bin/env python3
"""
Test the actual app's load_users function
"""
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Read the file directly
print("=" * 70)
print("File Contents")
print("=" * 70)
users_file = project_root / 'config' / 'users.json'
with open(users_file, 'r') as f:
    content = f.read()
    
print(content)
print()

# Parse and display
data = json.loads(content)
users = data.get('users', [])

print("=" * 70)
print(f"Parsed {len(users)} users")
print("=" * 70)

for i, user in enumerate(users, 1):
    print(f"\nUser {i}:")
    print(f"  Email: {user['email']}")
    print(f"  Code: {user['access_code']}")
    print(f"  Name: {user.get('name', 'N/A')}")
    print(f"  Role: {user.get('role', 'user')}")

# Test the exact authentication logic from app.py
print("\n" + "=" * 70)
print("Authentication Test")
print("=" * 70)

def authenticate_user(email, access_code, users):
    """Same logic as in app.py"""
    for user in users:
        if user['email'].lower() == email.lower() and user['access_code'] == access_code:
            return user
    return None

# Test User 2
test_email = "d3jualu.n@gmail.com"
test_code = "BxAD6bjaFkD4wwcCE38GFLHx"

print(f"\nTesting: {test_email}")
print(f"Code: {test_code}")
print(f"Code length: {len(test_code)}")
print(f"Code repr: {repr(test_code)}")

result = authenticate_user(test_email, test_code, users)

if result:
    print("\n✅ Authentication SUCCESSFUL")
    print(f"   Matched user: {result['name']}")
else:
    print("\n❌ Authentication FAILED")
    print("\nDebugging:")
    for i, user in enumerate(users, 1):
        email_match = user['email'].lower() == test_email.lower()
        code_match = user['access_code'] == test_code
        print(f"\n  User {i}: {user['name']}")
        print(f"    Email match: {email_match}")
        print(f"    Code match: {code_match}")
        if not code_match:
            print(f"    Expected: {repr(user['access_code'])}")
            print(f"    Got:      {repr(test_code)}")
            print(f"    Byte diff: {user['access_code'].encode()} vs {test_code.encode()}")
