#!/usr/bin/env python3
"""Check distinct cardinal number types in the database."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DB_TYPE'] = 'cosmos'

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Get distinct definitions containing 'cardinal'
pipeline = [
    {'$match': {'definition': {'$regex': 'cardinal', '$options': 'i'}}},
    {'$group': {'_id': '$definition', 'count': {'$sum': 1}}},
    {'$sort': {'count': -1}}
]
results = list(db.dictionary_collection.aggregate(pipeline))
print('Distinct cardinal number definitions:')
for r in results:
    print(f"  {r['count']:5} - {r['_id']}")

print("\n\nSample entries from each type:")
for r in results[:5]:
    defn = r['_id']
    samples = list(db.dictionary_collection.find({'definition': defn}).limit(3))
    print(f"\n--- {defn} ---")
    for s in samples:
        cw = s.get('chuukese_word', '')
        et = s.get('english_translation', '')
        print(f"  {cw:30} -> {et}")
