"""
Migration script to denormalize word family relationships
Adds 'related_words' array to each dictionary entry
"""
import os
import sys
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_factory import get_database_client, get_database_config

def migrate_denormalize_families():
    """Add related_words array to all dictionary entries"""
    
    # Connect to database using the same factory as the app
    config = get_database_config()
    client = get_database_client()
    db = client[config['database_name']]
    dictionary_collection = db[config['container_name']]
    
    print("🔍 Analyzing word families...")
    
    # Get total count first
    total_count = dictionary_collection.count_documents({})
    print(f"📊 Total entries in database: {total_count}")
    
    # Step 1: Build word family index
    word_families = defaultdict(list)  # base_word -> list of all related entries
    base_word_map = {}  # word -> its base word
    
    # Find all entries (including en_to_chk for complete family mapping)
    all_entries = list(dictionary_collection.find({}))
    
    print(f"📚 Processing {len(all_entries)} entries...")
    
    # Build the family index
    for entry in all_entries:
        word = entry.get('chuukese_word', '').lower().strip()
        translation = entry.get('english_translation', '')
        entry_id = str(entry['_id'])
        
        # Determine base word
        if entry.get('is_base_word'):
            base_word = word
            base_word_map[word] = word
        elif entry.get('base_word'):
            base_word = entry['base_word']
            base_word_map[word] = base_word
        elif entry.get('word_family'):
            base_word = entry['word_family']
            base_word_map[word] = base_word
        else:
            # No family info, treat as standalone
            base_word = word
            base_word_map[word] = word
        
        # Add to family
        word_families[base_word].append({
            'word': word,
            'translation': translation,
            'word_type': entry.get('word_type', ''),
            'entry_id': entry_id
        })
    
    print(f"👨‍👩‍👧‍👦 Found {len(word_families)} word families")
    
    # Step 2: Update each entry with its related words
    updated_count = 0
    skipped_count = 0
    
    for entry in all_entries:
        word = entry.get('chuukese_word', '').lower().strip()
        base_word = base_word_map.get(word, word)
        
        # Get all family members except self
        family_members = word_families.get(base_word, [])
        related_words = [
            {
                'word': member['word'],
                'translation': member['translation'],
                'word_type': member['word_type']
            }
            for member in family_members
            if member['word'] != word  # Exclude self
        ]
        
        # Update the entry
        update_data = {
            'related_words': related_words,
            'word_family_size': len(family_members),
            'base_word': base_word
        }
        
        # Only update if there are changes
        if entry.get('related_words') != related_words:
            dictionary_collection.update_one(
                {'_id': entry['_id']},
                {'$set': update_data}
            )
            updated_count += 1
            
            if updated_count % 100 == 0:
                print(f"  ✅ Updated {updated_count} entries...")
        else:
            skipped_count += 1
    
    print(f"\n✅ Migration complete!")
    print(f"  📝 Updated: {updated_count} entries")
    print(f"  ⏭️  Skipped: {skipped_count} entries (no changes)")
    
    # Show sample statistics
    family_sizes = [len(members) for members in word_families.values()]
    if family_sizes:
        avg_size = sum(family_sizes) / len(family_sizes)
        max_size = max(family_sizes)
        print(f"\n📊 Family Statistics:")
        print(f"  Average family size: {avg_size:.1f}")
        print(f"  Largest family: {max_size} members")
        
        # Show largest families
        largest_families = sorted(word_families.items(), key=lambda x: len(x[1]), reverse=True)[:5]
        print(f"\n🏆 Largest word families:")
        for base_word, members in largest_families:
            print(f"  {base_word}: {len(members)} members")
    
    client.close()

if __name__ == '__main__':
    try:
        migrate_denormalize_families()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
