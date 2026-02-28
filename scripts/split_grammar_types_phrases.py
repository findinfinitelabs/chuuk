#!/usr/bin/env python3
"""
Split grammar types in phrases_collection into core grammar + grammar_modifier fields.

This script migrates phrases_collection from single 'grammar' field to two fields:
- grammar: Core grammatical category (verb, noun, adjective, etc.)
- grammar_modifier: Optional modifier (transitive, locational, reduplicated, etc.)
"""

import sys
import json
import time
from typing import Dict, Tuple, Optional
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.dictionary_db import DictionaryDB


# Load the grammar mapping
MAPPING_FILE = str(Path(__file__).resolve().parent.parent / 'data' / 'grammar' / 'grammar_mapping.json')
with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
    mapping_data = json.load(f)
    GRAMMAR_MAPPING = mapping_data['mapping']


def split_grammar(original_grammar: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Split a grammar type into core and modifier using the mapping."""
    if not original_grammar:
        return None, None
    
    if original_grammar in GRAMMAR_MAPPING:
        mapping = GRAMMAR_MAPPING[original_grammar]
        return mapping['core'], mapping['modifier']
    
    print(f"⚠️  WARNING: No mapping found for '{original_grammar}' - keeping as-is")
    return original_grammar, None


def main():
    db = DictionaryDB()
    
    if not db.client:
        print("❌ Failed to connect to database")
        return
    
    print("\n" + "=" * 80)
    print("PHRASES COLLECTION - GRAMMAR TYPE MIGRATION")
    print("=" * 80)
    
    # Get all entries with grammar field
    query = {'grammar': {'$exists': True, '$ne': None, '$ne': ''}}
    
    try:
        entries = list(db.phrases_collection.find(query))
        print(f"📊 Found {len(entries):,} phrases with grammar field")
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        return
    
    if len(entries) == 0:
        print("No phrases to migrate.")
        return
    
    # Analyze grammar types
    print("\nAnalyzing grammar types...")
    grammar_types = {}
    for entry in entries:
        grammar = entry.get('grammar')
        if grammar not in grammar_types:
            core, modifier = split_grammar(grammar)
            grammar_types[grammar] = {
                'count': 0,
                'core': core,
                'modifier': modifier
            }
        grammar_types[grammar]['count'] += 1
    
    print(f"\nFound {len(grammar_types)} unique grammar types")
    print("\nTop grammar types:")
    for grammar, stats in sorted(grammar_types.items(), key=lambda x: -x[1]['count'])[:10]:
        print(f"  {grammar:<40} ({stats['count']:,} entries) → {stats['core']}, {stats['modifier']}")
    
    # Confirm
    confirm = input(f"\nMigrate {len(entries):,} phrases? Type 'YES' to continue: ")
    if confirm != 'YES':
        print("Migration cancelled.")
        return
    
    # Migrate in batches of 100
    print("\n" + "-" * 80)
    print("Migrating phrases in batches of 100...")
    print("-" * 80)
    
    success_count = 0
    error_count = 0
    batch_size = 100
    
    for batch_start in range(0, len(entries), batch_size):
        batch_end = min(batch_start + batch_size, len(entries))
        batch = entries[batch_start:batch_end]
        
        # Build bulk write operations
        from pymongo import UpdateOne
        
        bulk_operations = []
        for entry in batch:
            original_grammar = entry.get('grammar')
            core, modifier = split_grammar(original_grammar)
            
            bulk_operations.append(
                UpdateOne(
                    {'_id': entry['_id']},
                    {'$set': {
                        'grammar': core,
                        'grammar_modifier': modifier
                    }}
                )
            )
        
        # Execute bulk write
        try:
            result = db.phrases_collection.bulk_write(bulk_operations)
            success_count += result.modified_count
            print(f"  Processed {batch_end:,}/{len(entries):,} ({batch_end*100//len(entries)}%) - "
                  f"Batch: {result.modified_count} updated")
        except Exception as e:
            print(f"  ❌ Error in batch {batch_start}-{batch_end}: {e}")
            error_count += len(batch)
        
        time.sleep(0.5)  # 500ms delay between batches
    
    print("\n" + "=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print(f"✓ Successfully updated: {success_count:,} phrases")
    print(f"❌ Errors: {error_count}")


if __name__ == '__main__':
    main()
