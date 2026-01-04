#!/usr/bin/env python3
"""Check cardinal and ordinal number entries in the database."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DB_TYPE'] = 'cosmos'

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Check for cardinal numbers
print('=== CARDINAL NUMBERS ===')
cardinals = list(db.dictionary_collection.find({'definition': {'$regex': 'cardinal', '$options': 'i'}}).limit(20))
cardinal_count = db.dictionary_collection.count_documents({'definition': {'$regex': 'cardinal', '$options': 'i'}})
print(f'Found {cardinal_count} cardinal entries (showing first 20)')
for c in cardinals[:20]:
    cw = c.get('chuukese_word', '')
    et = c.get('english_translation', '')
    defn = c.get('definition', '')[:40]
    gr = c.get('grammar', '')
    print(f'{cw:30} -> {et:15} | {gr:15} | {defn}')

print()
print('=== ORDINAL NUMBERS ===')
ordinals = list(db.dictionary_collection.find({'definition': {'$regex': 'ordinal', '$options': 'i'}}).limit(20))
ordinal_count = db.dictionary_collection.count_documents({'definition': {'$regex': 'ordinal', '$options': 'i'}})
print(f'Found {ordinal_count} ordinal entries (showing first 20)')
for o in ordinals[:20]:
    cw = o.get('chuukese_word', '')
    et = o.get('english_translation', '')
    defn = o.get('definition', '')[:40]
    gr = o.get('grammar', '')
    print(f'{cw:30} -> {et:15} | {gr:15} | {defn}')

print()
print('=== TOTAL COUNTS ===')
print(f'Total cardinal entries: {cardinal_count}')
print(f'Total ordinal entries: {ordinal_count}')
