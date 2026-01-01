#!/usr/bin/env python3
"""Search for wor pattern and related words."""

import sys
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')

from src.database.dictionary_db import DictionaryDB

db_instance = DictionaryDB()
collection = db_instance.collection

# Search for words containing 'wor' in chuukese
print('=== wor pattern ===')
results = list(collection.find({
    'chuukese': {'$regex': 'wor', '$options': 'i'}
}).limit(20))
for r in results:
    print(f"  {r.get('chuukese', '')} = {r.get('english', '')}")

print('\n=== a wor in examples ===')
results = list(collection.find({
    '$or': [
        {'examples': {'$regex': 'a wor', '$options': 'i'}},
        {'chuukese': {'$regex': 'a wor', '$options': 'i'}},
    ]
}).limit(10))
for r in results:
    ch = r.get('chuukese', '')
    en = r.get('english', '')
    ex = r.get('examples', [])
    print(f"  {ch} = {en}")
    if ex:
        print(f"    Examples: {ex}")

print('\n=== eew/ew/eu (one) ===')
results = list(collection.find({
    'chuukese': {'$regex': '^e(u|w|ew)', '$options': 'i'}
}).limit(20))
for r in results:
    print(f"  {r.get('chuukese', '')} = {r.get('english', '')}")

print('\n=== won/woon (on) ===')
results = list(collection.find({
    'chuukese': {'$regex': '^woo?n', '$options': 'i'}
}).limit(10))
for r in results:
    print(f"  {r.get('chuukese', '')} = {r.get('english', '')}")
