#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')
from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Search more broadly
results = list(db.phrases_collection.find({'chuukese_word': {'$regex': 'aúfichiet', '$options': 'i'}}).limit(5))
print(f"Found {len(results)} phrases")

for phrase in results:
    print(f"\nChuukese: {phrase.get('chuukese_word') or phrase.get('chuukese_phrase')}")
    print(f"Grammar: {phrase.get('grammar')}")
    print(f"Modifier: {phrase.get('grammar_modifier')}")
    print(f"English: {phrase.get('english_translation')}")

