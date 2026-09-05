#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')
from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Check if phrases_collection has entries with grammar field
phrase_count = db.phrases_collection.count_documents({'grammar': {'$exists': True, '$ne': None, '$ne': ''}})
print(f'Phrases with grammar field: {phrase_count}')

# Find a sample phrase with grammar
phrase = db.phrases_collection.find_one({'grammar': {'$exists': True, '$ne': None, '$ne': ''}})
if phrase:
    print(f"\nSample phrase:")
    print(f"Chuukese: {phrase.get('chuukese_word') or phrase.get('chuukese_phrase') or phrase.get('chuukese_sentence')}")
    print(f"Grammar: {phrase.get('grammar')}")
    print(f"Modifier: {phrase.get('grammar_modifier')}")
    print(f"English: {phrase.get('english_translation')}")
