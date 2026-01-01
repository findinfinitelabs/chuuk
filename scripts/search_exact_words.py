#!/usr/bin/env python3
"""Search for exact word matches for sentence structure."""

import sys
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')

from src.database.dictionary_db import DictionaryDB

db_instance = DictionaryDB()
collection = db_instance.collection

# Search for specific words
words_to_find = ['wor', 'sanif', 'ewe', 'eu', 'woon', 'won', 'puk']
for word in words_to_find:
    print(f'\n=== {word} ===')
    results = collection.find({
        '$or': [
            {'chuukese': {'$regex': f'^{word}$', '$options': 'i'}},
            {'english': {'$regex': f'^{word}$', '$options': 'i'}},
        ]
    }).limit(10)
    for r in results:
        ch = r.get('chuukese', '')
        en = r.get('english', '')
        print(f'  {ch} = {en}')

# Also search for "shelf" and "book" in English
print('\n=== shelf (English) ===')
results = collection.find({
    'english': {'$regex': 'shelf', '$options': 'i'}
}).limit(10)
for r in results:
    ch = r.get('chuukese', '')
    en = r.get('english', '')
    print(f'  {ch} = {en}')

print('\n=== book (English) ===')
results = collection.find({
    'english': {'$regex': '^book$', '$options': 'i'}
}).limit(10)
for r in results:
    ch = r.get('chuukese', '')
    en = r.get('english', '')
    print(f'  {ch} = {en}')

# Search for "exist" or "there is" patterns
print('\n=== exist/there is ===')
results = collection.find({
    '$or': [
        {'english': {'$regex': 'exist', '$options': 'i'}},
        {'english': {'$regex': 'there is', '$options': 'i'}},
        {'english': {'$regex': 'there are', '$options': 'i'}},
    ]
}).limit(15)
for r in results:
    ch = r.get('chuukese', '')
    en = r.get('english', '')
    print(f'  {ch} = {en}')

# Search for classifiers/counters
print('\n=== Numbers with classifiers ===')
classifiers = ['eu', 'eew', 'efoch', 'ewen', 'ew']
for clf in classifiers:
    results = collection.find({
        'chuukese': {'$regex': f'^{clf}$', '$options': 'i'}
    }).limit(5)
    for r in results:
        ch = r.get('chuukese', '')
        en = r.get('english', '')
        print(f'  {ch} = {en}')
