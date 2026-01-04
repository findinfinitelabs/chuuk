#!/usr/bin/env python3
"""
Export all number entries (1-1000) from the database to a TSV file for review.
"""

import os
import sys
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DB_TYPE'] = 'cosmos'

from src.database.dictionary_db import DictionaryDB

def export_numbers():
    db = DictionaryDB()
    
    if not db.client:
        print("❌ Failed to connect to database")
        return
    
    # Query for entries that look like numbers (grammar contains 'number' or type contains 'number')
    # Also look for entries with numeric translations
    query = {
        '$or': [
            {'grammar': {'$regex': 'number', '$options': 'i'}},
            {'type': {'$regex': 'number', '$options': 'i'}},
            {'definition': {'$regex': 'number', '$options': 'i'}},
            {'english_translation': {'$regex': '^\\d+$'}},  # Just digits
            {'english_translation': 'ordinal number'},
        ]
    }
    
    results = list(db.dictionary_collection.find(query).sort('english_translation', 1))
    print(f"Found {len(results)} number-related entries")
    
    # Also search phrases collection
    phrase_results = list(db.phrases_collection.find(query).sort('english_translation', 1))
    print(f"Found {len(phrase_results)} number-related phrase entries")
    
    all_results = results + phrase_results
    
    # Sort by numeric value if possible
    def sort_key(entry):
        trans = entry.get('english_translation', '')
        try:
            return (0, int(trans))
        except (ValueError, TypeError):
            return (1, trans)
    
    all_results.sort(key=sort_key)
    
    # Write to TSV
    output_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output', 'numbers_export.tsv')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['_id', 'chuukese_word', 'english_translation', 'definition', 'grammar', 'type', 'collection'])
        
        for r in all_results:
            # Determine which collection this came from
            collection = 'dictionary' if r in results else 'phrases'
            
            writer.writerow([
                str(r.get('_id', '')),
                r.get('chuukese_word', '') or r.get('chuukese_sentence', '') or r.get('chuukese_phrase', ''),
                r.get('english_translation', ''),
                r.get('definition', ''),
                r.get('grammar', ''),
                r.get('type', ''),
                collection
            ])
    
    print(f"\n✅ Exported {len(all_results)} entries to: {output_file}")
    
    # Also print summary of problematic entries
    print("\n📊 Entries with 'ordinal number' as translation:")
    ordinal_entries = [r for r in all_results if r.get('english_translation') == 'ordinal number']
    for r in ordinal_entries[:30]:
        print(f"  {r.get('chuukese_word', '')} = {r.get('english_translation', '')}")
    if len(ordinal_entries) > 30:
        print(f"  ... and {len(ordinal_entries) - 30} more")
    
    print(f"\nTotal with 'ordinal number' translation: {len(ordinal_entries)}")


if __name__ == '__main__':
    export_numbers()
