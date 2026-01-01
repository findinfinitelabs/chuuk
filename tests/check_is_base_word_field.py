#!/usr/bin/env python3
from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Check how many entries have the is_base_word field
with_field = db.dictionary_collection.count_documents({'is_base_word': {'$exists': True}})
total = db.dictionary_collection.count_documents({})

print(f'Entries with is_base_word field: {with_field} / {total}')

if with_field > 0:
    print('\nSample entries with is_base_word=True:')
    samples_true = list(db.dictionary_collection.find({'is_base_word': True}).limit(5))
    for s in samples_true:
        print(f"  • {s['chuukese_word']} ({s.get('grammar', 'no grammar')}) = {s.get('english_translation', '')}")
    
    print('\nSample entries with is_base_word=False:')
    samples_false = list(db.dictionary_collection.find({'is_base_word': False}).limit(5))
    for s in samples_false:
        print(f"  • {s['chuukese_word']} ({s.get('grammar', 'no grammar')}) = {s.get('english_translation', '')}")
else:
    print('\n⚠️  The is_base_word field does not exist in any entries.')
    print('This means we need to use logic to determine which words are base words.')
