#!/usr/bin/env python3
"""
Update number_type field to distinguish between base cardinal and cardinal numbers.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DB_TYPE'] = 'cosmos'

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Update "base cardinal number" entries
base_query = {'definition': 'base cardinal number'}
base_count = db.dictionary_collection.count_documents(base_query)
print(f"Found {base_count} 'base cardinal number' entries")

# Update "cardinal number" entries (not base)
cardinal_query = {'definition': 'cardinal number'}
cardinal_count = db.dictionary_collection.count_documents(cardinal_query)
print(f"Found {cardinal_count} 'cardinal number' entries")

confirm = input(f"\nUpdate number_type for {base_count + cardinal_count} entries? (yes/no): ")
if confirm.lower() != 'yes':
    print("❌ Cancelled")
    sys.exit(0)

# Update base cardinal numbers
print("\nUpdating base cardinal numbers...")
base_entries = list(db.dictionary_collection.find(base_query))
updated = 0
for entry in base_entries:
    try:
        db.dictionary_collection.update_one(
            {'_id': entry['_id']},
            {'$set': {'number_type': 'base_cardinal'}}
        )
        updated += 1
        if updated % 100 == 0:
            print(f"  Updated {updated}/{len(base_entries)}...")
            time.sleep(0.1)
    except Exception as e:
        print(f"  Error: {e}")
        time.sleep(0.5)
print(f"✅ Updated {updated} base cardinal entries")

# Update cardinal numbers (classifier-based)
print("\nUpdating cardinal numbers...")
cardinal_entries = list(db.dictionary_collection.find(cardinal_query))
updated = 0
for entry in cardinal_entries:
    try:
        db.dictionary_collection.update_one(
            {'_id': entry['_id']},
            {'$set': {'number_type': 'cardinal'}}
        )
        updated += 1
        if updated % 100 == 0:
            print(f"  Updated {updated}/{len(cardinal_entries)}...")
            time.sleep(0.1)
    except Exception as e:
        print(f"  Error: {e}")
        time.sleep(0.5)
print(f"✅ Updated {updated} cardinal entries")

# Verify
print("\n=== Verification ===")
base_sample = list(db.dictionary_collection.find({'number_type': 'base_cardinal'}).limit(5))
print("\nBase cardinal samples:")
for s in base_sample:
    print(f"  {s.get('chuukese_word'):25} -> {s.get('english_translation'):5} | sort: {s.get('sort_order')} | type: {s.get('number_type')}")

cardinal_sample = list(db.dictionary_collection.find({'number_type': 'cardinal'}).limit(5))
print("\nCardinal samples:")
for s in cardinal_sample:
    print(f"  {s.get('chuukese_word'):25} -> {s.get('english_translation'):5} | sort: {s.get('sort_order')} | type: {s.get('number_type')}")

# Count by type
print("\n=== Counts by number_type ===")
for nt in ['base_cardinal', 'cardinal']:
    count = db.dictionary_collection.count_documents({'number_type': nt})
    print(f"  {nt}: {count}")
