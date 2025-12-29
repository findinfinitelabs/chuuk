#!/usr/bin/env python3
"""
User Management Utility for Chuuk Dictionary
Generates secure access codes and manages users in config/users.json
"""
import os
import sys
import json
import secrets
import string
import argparse
from pathlib import Path

# Config file path
CONFIG_DIR = Path(__file__).parent.parent / 'config'
USERS_FILE = CONFIG_DIR / 'users.json'


def generate_access_code(length: int = 24) -> str:
    """Generate a cryptographically secure access code"""
    # Use a mix of uppercase, lowercase, and digits (no ambiguous chars)
    alphabet = string.ascii_letters + string.digits
    # Remove ambiguous characters: 0, O, l, 1, I
    alphabet = alphabet.replace('0', '').replace('O', '').replace('l', '').replace('1', '').replace('I', '')
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def load_users() -> dict:
    """Load existing users from config file"""
    if USERS_FILE.exists():
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {'users': []}


def save_users(data: dict) -> None:
    """Save users to config file"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Users saved to {USERS_FILE}")


def add_user(email: str, name: str = None, role: str = 'user') -> str:
    """Add a new user with a generated access code"""
    data = load_users()
    
    # Check if user already exists
    for user in data['users']:
        if user['email'].lower() == email.lower():
            print(f"❌ User with email '{email}' already exists")
            return None
    
    # Generate secure access code
    access_code = generate_access_code()
    
    # Create user entry
    new_user = {
        'email': email,
        'access_code': access_code,
        'name': name or email.split('@')[0],
        'role': role
    }
    
    data['users'].append(new_user)
    save_users(data)
    
    print(f"\n✅ User added successfully!")
    print(f"   Email: {email}")
    print(f"   Name: {new_user['name']}")
    print(f"   Role: {role}")
    print(f"   Access Code: {access_code}")
    print(f"\n⚠️  Save this access code securely - it cannot be recovered!")
    
    return access_code


def list_users() -> None:
    """List all users (without showing access codes)"""
    data = load_users()
    
    if not data['users']:
        print("No users configured.")
        return
    
    print(f"\n{'Email':<40} {'Name':<20} {'Role':<10}")
    print("-" * 70)
    for user in data['users']:
        print(f"{user['email']:<40} {user.get('name', 'N/A'):<20} {user.get('role', 'user'):<10}")
    print(f"\nTotal: {len(data['users'])} users")


def remove_user(email: str) -> bool:
    """Remove a user by email"""
    data = load_users()
    
    original_count = len(data['users'])
    data['users'] = [u for u in data['users'] if u['email'].lower() != email.lower()]
    
    if len(data['users']) < original_count:
        save_users(data)
        print(f"✅ User '{email}' removed")
        return True
    else:
        print(f"❌ User '{email}' not found")
        return False


def regenerate_code(email: str) -> str:
    """Regenerate access code for an existing user"""
    data = load_users()
    
    for user in data['users']:
        if user['email'].lower() == email.lower():
            new_code = generate_access_code()
            user['access_code'] = new_code
            save_users(data)
            print(f"\n✅ Access code regenerated for {email}")
            print(f"   New Access Code: {new_code}")
            print(f"\n⚠️  Save this access code securely - it cannot be recovered!")
            return new_code
    
    print(f"❌ User '{email}' not found")
    return None


def main():
    parser = argparse.ArgumentParser(
        description='User Management Utility for Chuuk Dictionary',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manage_users.py add user@example.com --name "John Doe" --role admin
  python manage_users.py list
  python manage_users.py regenerate user@example.com
  python manage_users.py remove user@example.com
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add user command
    add_parser = subparsers.add_parser('add', help='Add a new user')
    add_parser.add_argument('email', help='User email address')
    add_parser.add_argument('--name', '-n', help='User display name')
    add_parser.add_argument('--role', '-r', default='user', choices=['user', 'translator', 'admin'], 
                           help='User role: user (basic), translator (no publications), admin (full access)')
    
    # List users command
    subparsers.add_parser('list', help='List all users')
    
    # Remove user command
    remove_parser = subparsers.add_parser('remove', help='Remove a user')
    remove_parser.add_argument('email', help='User email address')
    
    # Regenerate code command
    regen_parser = subparsers.add_parser('regenerate', help='Regenerate access code for a user')
    regen_parser.add_argument('email', help='User email address')
    
    # Generate code only (for testing)
    gen_parser = subparsers.add_parser('generate', help='Generate a random access code (for testing)')
    gen_parser.add_argument('--length', '-l', type=int, default=24, help='Code length')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        add_user(args.email, args.name, args.role)
    elif args.command == 'list':
        list_users()
    elif args.command == 'remove':
        remove_user(args.email)
    elif args.command == 'regenerate':
        regenerate_code(args.email)
    elif args.command == 'generate':
        code = generate_access_code(args.length)
        print(f"Generated code: {code}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
