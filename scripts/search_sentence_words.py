#!/usr/bin/env python3
"""Search for sentence structure words in the dictionary."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_factory import get_database_client, get_database_config

config = get_database_config()
client = get_database_client()
db = client[config['database_name']]
collection = db['dictionary_entries']

words = ['wor', 'sanif', 'puk', 'shelf', 'book', 'exist', 'there', 'is', 'on', 'the']

for word in words:
    results = list(collection.find({
        '$or': [
            {'chuukese_word': {'$regex': word, '$options': 'i'}},
            {'english_translation': {'$regex': word, '$options': 'i'}}
        ]
    }).limit(8))
    if results:
        print(f'=== {word} ===')
        for r in results:
            chuukese = r.get('chuukese_word', 'N/A')
            english = r.get('english_translation', 'N/A')
            if english:
                english = english[:100]
            print(f"  {chuukese} = {english}")
        print()
