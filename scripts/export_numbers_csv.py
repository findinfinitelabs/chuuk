#!/usr/bin/env python3
"""
Export ordinal and cardinal number entries from the database to CSV files.
"""

import os
import sys
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DB_TYPE'] = 'cosmos'

from src.database.dictionary_db import DictionaryDB


def export_numbers_to_csv():
    db = DictionaryDB()
    
    if not db.client:
        print("❌ Failed to connect to database")
        return
    
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'numbers')
    os.makedirs(output_dir, exist_ok=True)
    
    # Query for ordinal numbers - look for "ordinal number" in definition
    ordinal_query = {
        'definition': {'$regex': 'ordinal number', '$options': 'i'}
    }
    
    # Query for cardinal numbers - look for "cardinal number" in definition
    cardinal_query = {
        'definition': {'$regex': 'cardinal number', '$options': 'i'}
    }
    
    # Get ordinal results from dictionary and phrases collections
    ordinal_dict = list(db.dictionary_collection.find(ordinal_query))
    ordinal_phrases = list(db.phrases_collection.find(ordinal_query))
    all_ordinals = ordinal_dict + ordinal_phrases
    
    # Get cardinal results from dictionary and phrases collections
    cardinal_dict = list(db.dictionary_collection.find(cardinal_query))
    cardinal_phrases = list(db.phrases_collection.find(cardinal_query))
    all_cardinals = cardinal_dict + cardinal_phrases
    
    print(f"Found {len(all_ordinals)} ordinal number entries")
    print(f"Found {len(all_cardinals)} cardinal number entries")
    
    # Export ordinal numbers
    ordinal_file = os.path.join(output_dir, 'ordinal_numbers.csv')
    write_csv(ordinal_file, all_ordinals, ordinal_dict)
    print(f"✅ Exported {len(all_ordinals)} ordinal entries to: {ordinal_file}")
    
    # Export cardinal numbers
    cardinal_file = os.path.join(output_dir, 'cardinal_numbers.csv')
    write_csv(cardinal_file, all_cardinals, cardinal_dict)
    print(f"✅ Exported {len(all_cardinals)} cardinal entries to: {cardinal_file}")
    
    # Also create a combined file
    all_numbers = all_ordinals + all_cardinals
    # Remove duplicates based on _id
    seen_ids = set()
    unique_numbers = []
    for entry in all_numbers:
        entry_id = str(entry.get('_id', ''))
        if entry_id not in seen_ids:
            seen_ids.add(entry_id)
            unique_numbers.append(entry)
    
    combined_file = os.path.join(output_dir, 'all_numbers.csv')
    write_csv(combined_file, unique_numbers, ordinal_dict + cardinal_dict)
    print(f"✅ Exported {len(unique_numbers)} total unique entries to: {combined_file}")


def write_csv(filepath, entries, dict_entries):
    """Write entries to a CSV file."""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'chuukese_word', 
            'english_translation', 
            'definition', 
            'grammar', 
            'type',
            'source',
            'collection'
        ])
        
        for entry in entries:
            # Determine which collection this came from
            collection = 'dictionary' if entry in dict_entries else 'phrases'
            
            # Get the Chuukese word/phrase
            chuukese = (
                entry.get('chuukese_word', '') or 
                entry.get('chuukese_sentence', '') or 
                entry.get('chuukese_phrase', '') or
                entry.get('chuukese', '')
            )
            
            writer.writerow([
                chuukese,
                entry.get('english_translation', ''),
                entry.get('definition', ''),
                entry.get('grammar', ''),
                entry.get('type', ''),
                entry.get('source', ''),
                collection
            ])


if __name__ == '__main__':
    export_numbers_to_csv()
