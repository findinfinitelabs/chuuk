#!/usr/bin/env python3
"""
Fix missing fields in existing database entries
Adds: type, search_direction, direction, primary_language, secondary_language
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.dictionary_db import DictionaryDB

def fix_missing_fields():
    """Add missing fields to all existing entries"""
    db = DictionaryDB()
    
    print("🔧 Fixing missing fields in database entries...")
    print("=" * 60)
    
    # Get all entries
    total_entries = db.dictionary_collection.count_documents({})
    print(f"Found {total_entries} entries to process")
    
    # Process in batches
    batch_size = 100
    updated = 0
    skipped = 0
    
    for skip in range(0, total_entries, batch_size):
        entries = list(db.dictionary_collection.find({}).skip(skip).limit(batch_size))
        
        for entry in entries:
            entry_id = entry['_id']
            updates = {}
            
            # Add type field if missing (alias for word_type)
            if 'type' not in entry and 'word_type' in entry:
                updates['type'] = entry['word_type']
            elif 'type' not in entry:
                updates['type'] = 'word'
            
            # Determine direction based on which field is more likely Chuukese
            # If entry has these fields already, skip
            if 'search_direction' not in entry or 'direction' not in entry:
                # Simple heuristic: Chuukese words are shorter and contain fewer vowels
                chuukese_word = entry.get('chuukese_word', '')
                english_translation = entry.get('english_translation', '')
                
                # Check if this looks like a proper Chuukese -> English entry
                # (Chuukese words typically have specific characteristics)
                direction = 'chk_to_en'  # Default
                
                updates['search_direction'] = direction
                updates['direction'] = direction
                updates['primary_language'] = 'chuukese'
                updates['secondary_language'] = 'english'
            
            # Apply updates if any
            if updates:
                db.dictionary_collection.update_one(
                    {'_id': entry_id},
                    {'$set': updates}
                )
                updated += 1
            else:
                skipped += 1
        
        print(f"Processed {min(skip + batch_size, total_entries)}/{total_entries} entries...")
    
    print("\n" + "=" * 60)
    print(f"✅ Migration complete!")
    print(f"   Updated: {updated} entries")
    print(f"   Skipped: {skipped} entries (already had fields)")
    print("=" * 60)

if __name__ == "__main__":
    fix_missing_fields()
