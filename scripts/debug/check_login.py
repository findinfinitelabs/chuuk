#!/usr/bin/env python3
"""
Test login for both users
"""
import os
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def load_users():
    """Load users from config file"""
    users_file = project_root / 'config' / 'users.json'
    with open(users_file, 'r') as f:
        data = json.load(f)
        return data.get('users', [])

def authenticate_user(email, access_code):
    """Simulate the authentication process from app.py"""
    users = load_users()
    for user in users:
        print(f"  Checking: {user['email']}")
        print(f"    Email match (case-insensitive): {user['email'].lower() == email.lower()}")
        print(f"    Access code match: {user['access_code'] == access_code}")
        print(f"    Expected: '{user['access_code']}'")
        print(f"    Provided: '{access_code}'")
        
        if user['email'].lower() == email.lower() and user['access_code'] == access_code:
            return user
    return None

# Test both users
print("=" * 70)
print("Testing User 1: Chris Lundy")
print("=" * 70)
email1 = "chris.lundy@findinfinite.com"
code1 = "BxAD6bjaFkD4wwcCE38GFLHw"
print(f"Email: {email1}")
print(f"Code:  {code1}")
print()
result1 = authenticate_user(email1, code1)
if result1:
    print("✅ Authentication SUCCESSFUL")
else:
    print("❌ Authentication FAILED")

print("\n" + "=" * 70)
print("Testing User 2: Debora Lundy")
print("=" * 70)
email2 = os.environ.get("CHUUK_DEBUG_EMAIL", "")
code2 = os.environ.get("CHUUK_DEBUG_ACCESS_CODE", "")
print(f"Email: {email2}")
print(f"Code:  {code2}")
print()
result2 = authenticate_user(email2, code2)
if result2:
    print("✅ Authentication SUCCESSFUL")
else:
    print("❌ Authentication FAILED")

# Try with some common typos
print("\n" + "=" * 70)
print("Testing Common Issues")
print("=" * 70)

# Test case sensitivity
print("\nTest: Email with different case")
result = authenticate_user("D3JUALU.N@GMAIL.COM", code2)
print(f"Result: {'✅ PASS' if result else '❌ FAIL'}")

# Test with extra space
print("\nTest: Access code with trailing space")
result = authenticate_user(email2, code2 + " ")
print(f"Result: {'❌ FAIL (expected)' if not result else '⚠️ UNEXPECTED PASS'}")

# Display raw bytes
print("\n" + "=" * 70)
print("Raw Access Codes (for debugging)")
print("=" * 70)
users = load_users()
for i, user in enumerate(users, 1):
    print(f"\nUser {i}: {user['name']}")
    print(f"  Email: {user['email']}")
    print(f"  Access Code: {user['access_code']}")
    print(f"  Code bytes: {user['access_code'].encode('utf-8')}")
    print(f"  Code length: {len(user['access_code'])}")
