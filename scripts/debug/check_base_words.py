#!/usr/bin/env python3
from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()
base_words = list(db.dictionary_collection.find({'is_base_word': True}).limit(10))

print('Examples of base words (shown in dark purple, bold on Database page):')
print('=' * 70)
for w in base_words:
    if w:
        grammar = w.get('grammar', 'no grammar')
        print(f"  • {w['chuukese_word']} ({grammar}) = {w['english_translation']}")
