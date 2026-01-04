#!/usr/bin/env python3
"""
Add sort_order and number_type fields to cardinal number entries.
Excludes cardinal directions (north, south, east, west, etc.)
"""

import os
import sys
import time
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DB_TYPE'] = 'cosmos'

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Find cardinal number entries, excluding cardinal directions
query = {
    '$and': [
        {'definition': {'$regex': 'cardinal number', '$options': 'i'}},
        {'definition': {'$not': {'$regex': 'cardinal direction', '$options': 'i'}}}
    ]
}

entries = list(db.dictionary_collection.find(query))
print(f"Found {len(entries)} cardinal number entries (excluding directions)")

# Show a few examples first
print("\nSample entries to be updated:")
for e in entries[:10]:
    cw = e.get('chuukese_word', '')
    et = e.get('english_translation', '')
    defn = e.get('definition', '')[:50]
    print(f"  {cw:30} -> {et:10} | {defn}")

confirm = input(f"\nAdd sort_order and number_type to {len(entries)} entries? (yes/no): ")
if confirm.lower() != 'yes':
    print("❌ Cancelled")
    sys.exit(0)

updated = 0
errors = 0

for entry in entries:
    try:
        english = entry.get('english_translation', '')
        definition = entry.get('definition', '')
        
        # Parse the numeric value from english_translation
        # Handle cases like "1", "10", "100", "1000"
        try:
            sort_order = int(english)
        except (ValueError, TypeError):
            # If not a pure number, try to extract first number
            match = re.search(r'\d+', str(english))
            if match:
                sort_order = int(match.group())
            else:
                sort_order = 99999  # Put non-numeric at the end
        
        # Determine number_type based on definition
        definition_lower = definition.lower()
        if 'base cardinal' in definition_lower:
            number_type = 'base'
        elif 'animate' in definition_lower or 'living' in definition_lower:
            number_type = 'animate'
        elif 'long' in definition_lower:
            number_type = 'long_objects'
        elif 'round' in definition_lower:
            number_type = 'round_objects'
        elif 'flat' in definition_lower:
            number_type = 'flat_objects'
        else:
            number_type = 'cardinal'  # Generic cardinal
        
        # Update the document
        db.dictionary_collection.update_one(
            {'_id': entry['_id']},
            {'$set': {
                'sort_order': sort_order,
                'number_type': number_type
            }}
        )
        updated += 1
        
        if updated % 50 == 0:
            print(f"  Updated {updated}/{len(entries)}...")
            time.sleep(0.1)  # Avoid rate limiting
            
    except Exception as e:
        print(f"  Error updating {entry.get('chuukese_word')}: {e}")
        errors += 1
        time.sleep(0.5)

print(f"\n✅ Updated {updated} entries")
if errors:
    print(f"⚠️  {errors} errors occurred")

# Verify the update
print("\n=== Verification ===")
sample = list(db.dictionary_collection.find(
    {'sort_order': {'$exists': True}}
).sort('sort_order', 1).limit(15))

print("First 15 entries sorted by sort_order:")
for s in sample:
    cw = s.get('chuukese_word', '')
    et = s.get('english_translation', '')
    so = s.get('sort_order', '')
    nt = s.get('number_type', '')
    print(f"  {so:5} | {nt:15} | {cw:30} -> {et}")
