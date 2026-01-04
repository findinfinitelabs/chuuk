#!/usr/bin/env python3
"""Check for numeral classifier entries in the database."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DB_TYPE'] = 'cosmos'

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Look for classifier entries
classifiers = list(db.dictionary_collection.find({
    '$or': [
        {'grammar': {'$regex': 'classifier', '$options': 'i'}},
        {'definition': {'$regex': 'classifier|counting|round|long|flat', '$options': 'i'}},
        {'type': {'$regex': 'classifier', '$options': 'i'}}
    ]
}).limit(30))

print(f'Found {len(classifiers)} classifier entries')
for c in classifiers[:20]:
    cw = c.get('chuukese_word', '')
    et = c.get('english_translation', '')
    defn = c.get('definition', '')[:60]
    gr = c.get('grammar', '')
    print(f'{cw:25} -> {et:20} | {gr:15} | {defn}')

# Also check for ordinal patterns like "first", "second"
print("\n\n--- True ordinals (first, second, etc.) ---")
ordinals = list(db.dictionary_collection.find({
    '$or': [
        {'english_translation': {'$regex': '^first$|^second$|^third$|^fourth$|^fifth$', '$options': 'i'}},
        {'definition': {'$regex': 'first|second|third|position|order', '$options': 'i'}},
        {'grammar': {'$regex': 'ordinal', '$options': 'i'}}
    ]
}).limit(30))

print(f'Found {len(ordinals)} true ordinal entries')
for o in ordinals[:20]:
    cw = o.get('chuukese_word', '')
    et = o.get('english_translation', '')
    defn = o.get('definition', '')[:50]
    gr = o.get('grammar', '')
    print(f'{cw:25} -> {et:20} | {gr:15} | {defn}')
