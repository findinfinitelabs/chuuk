#!/usr/bin/env python3
"""Check dictionary entries in database."""
import sys
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Count entries
count = db.dictionary_collection.count_documents({})
print(f"📊 Total dictionary entries: {count}")

# Count CSV-uploaded entries
csv_count = db.dictionary_collection.count_documents({'source_type': 'csv_upload'})
print(f"📄 CSV-uploaded entries: {csv_count}")

# Show sample entries  
entries = list(db.dictionary_collection.find({'source_type': 'csv_upload'}).limit(5))
print("\n📚 Sample CSV-uploaded entries:")
for e in entries:
    word = e.get('chuukese_word', '')
    translation = e.get('english_translation', '')
    pos = e.get('part_of_speech', '')
    print(f"  • {word} = {translation} ({pos})")
