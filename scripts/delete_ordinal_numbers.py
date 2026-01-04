#!/usr/bin/env python3
"""Delete entries with 'ordinal number' in the definition field."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DB_TYPE'] = 'cosmos'

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Find all entries with "ordinal number" in definition
query = {'definition': 'ordinal number'}

# Count first
count = db.dictionary_collection.count_documents(query)
print(f"Found {count} entries with definition 'ordinal number'")

if count > 0:
    confirm = input(f"Delete all {count} entries? (yes/no): ")
    if confirm.lower() == 'yes':
        # Delete one at a time to avoid Cosmos DB rate limiting
        deleted = 0
        entries = list(db.dictionary_collection.find(query))
        for entry in entries:
            try:
                db.dictionary_collection.delete_one({'_id': entry['_id']})
                deleted += 1
                if deleted % 10 == 0:
                    print(f"  Deleted {deleted}/{len(entries)}...")
                    time.sleep(0.1)  # Small delay to avoid rate limiting
            except Exception as e:
                print(f"  Error deleting {entry.get('chuukese_word')}: {e}")
                time.sleep(1)  # Longer delay on error
        print(f"✅ Deleted {deleted} entries from dictionary collection")
        
        # Also check phrases collection
        phrase_entries = list(db.phrases_collection.find(query))
        if phrase_entries:
            deleted2 = 0
            for entry in phrase_entries:
                try:
                    db.phrases_collection.delete_one({'_id': entry['_id']})
                    deleted2 += 1
                    if deleted2 % 10 == 0:
                        time.sleep(0.1)
                except Exception as e:
                    print(f"  Error: {e}")
                    time.sleep(1)
            print(f"✅ Deleted {deleted2} entries from phrases collection")
        else:
            print("No matching entries in phrases collection")
    else:
        print("❌ Cancelled")
else:
    print("No entries to delete")
