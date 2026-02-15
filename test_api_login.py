#!/usr/bin/env python3
"""
Test the actual login API endpoint
"""
import requests
import json

# Test endpoint
url = "http://localhost:5000/api/auth/login"

print("=" * 70)
print("Testing Login API Endpoint")
print("=" * 70)

# Test User 2
print("\nTesting User 2: Debora Lundy")
print("-" * 70)

email = "d3jualu.n@gmail.com"
access_code = "BxAD6bjaFkD4wwcCE38GFLHx"

payload = {
    "email": email,
    "access_code": access_code,
    "terms_accepted": True,
    "terms_accepted_at": "2026-01-24T17:20:33.906Z"
}

print(f"Email: {email}")
print(f"Access Code: {access_code}")
print(f"\nPayload: {json.dumps(payload, indent=2)}")

try:
    print("\nSending request to:", url)
    response = requests.post(url, json=payload, timeout=5)
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("\n✅ Login SUCCESSFUL!")
    else:
        print(f"\n❌ Login FAILED: {response.json().get('error', 'Unknown error')}")
        
except requests.exceptions.ConnectionError:
    print("\n❌ ERROR: Cannot connect to http://localhost:5000")
    print("   Is the Flask app running?")
    print("   Start it with: python3 app.py")
except Exception as e:
    print(f"\n❌ ERROR: {e}")

# Also test User 1 for comparison
print("\n" + "=" * 70)
print("Testing User 1: Chris Lundy (for comparison)")
print("-" * 70)

email1 = "chris.lundy@findinfinite.com"
code1 = "BxAD6bjaFkD4wwcCE38GFLHw"

payload1 = {
    "email": email1,
    "access_code": code1,
    "terms_accepted": True,
    "terms_accepted_at": "2026-01-24T17:20:33.906Z"
}

print(f"Email: {email1}")
print(f"Access Code: {code1}")

try:
    response = requests.post(url, json=payload1, timeout=5)
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Login SUCCESSFUL!")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"❌ Login FAILED: {response.json().get('error', 'Unknown error')}")
        
except requests.exceptions.ConnectionError:
    print("\n❌ ERROR: Cannot connect to server")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
