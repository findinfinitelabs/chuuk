#!/usr/bin/env python3
"""
Split grammar types into core grammar + grammar_modifier fields.

This script migrates the database from single 'grammar' field to two fields:
- grammar: Core grammatical category (verb, noun, adjective, etc.)
- grammar_modifier: Optional modifier (transitive, locational, reduplicated, etc.)

Examples:
  "transitive verb" → grammar="verb", grammar_modifier="transitive"
  "noun + possessive" → grammar="noun", grammar_modifier="possessive"
  "verb (reduplicated)" → grammar="verb", grammar_modifier="reduplicated"
  "adjective" → grammar="adjective", grammar_modifier=None
"""

import sys
import json
import time
from typing import Dict, Tuple, Optional
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')

from src.database.dictionary_db import DictionaryDB


# Load the grammar mapping
MAPPING_FILE = '/Users/findinfinitelabs/DevApps/chuuk/data/grammar/grammar_mapping.json'
with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
    mapping_data = json.load(f)
    GRAMMAR_MAPPING = mapping_data['mapping']


def split_grammar(original_grammar: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Split a grammar type into core and modifier using the mapping.
    
    Args:
        original_grammar: Original grammar string (e.g., "transitive verb")
        
    Returns:
        Tuple of (core_grammar, grammar_modifier)
    """
    if not original_grammar:
        return None, None
    
    # Check if we have a direct mapping
    if original_grammar in GRAMMAR_MAPPING:
        mapping = GRAMMAR_MAPPING[original_grammar]
        return mapping['core'], mapping['modifier']
    
    # If not in mapping, return as-is (shouldn't happen with complete mapping)
    print(f"⚠️  WARNING: No mapping found for '{original_grammar}' - keeping as-is")
    return original_grammar, None


def migrate_grammar_types(dry_run: bool = True, max_entries: int = None, skip_confirm: bool = False):
    """
    Migrate all grammar types in the database to split format.
    
    Args:
        dry_run: If True, only preview changes without modifying database
        max_entries: Limit number of entries to process (for testing)
        skip_confirm: If True, skip the confirmation prompt
    """
    db = DictionaryDB()
    
    if not db.client:
        print("❌ Failed to connect to database")
        return
    
    print("\n" + "=" * 80)
    print("GRAMMAR TYPE MIGRATION - SPLIT INTO CORE + MODIFIER")
    print("=" * 80)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made to the database")
    else:
        print("⚠️  LIVE MODE - Database will be modified!")
        if not skip_confirm:
            print("   Make sure you have a backup before proceeding.")
            confirm = input("\nType 'YES' to continue: ")
            if confirm != 'YES':
                print("Migration cancelled.")
                return
        else:
            print("   Confirmation skipped (--yes flag)")
            time.sleep(1)  # Brief pause to read the warning
    
    print("\n" + "-" * 80)
    print("PHASE 1: Analyzing current grammar types")
    print("-" * 80)
    
    # Get all entries with grammar field
    query = {'grammar': {'$exists': True, '$ne': None, '$ne': ''}}
    
    try:
        if max_entries:
            entries = list(db.dictionary_collection.find(query).limit(max_entries))
        else:
            total_count = db.dictionary_collection.count_documents(query)
            print(f"📊 Found {total_count:,} entries with grammar field")
            entries = list(db.dictionary_collection.find(query))
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        return
    
    # Analyze what changes will be made
    grammar_stats = {}
    changes_preview = []
    
    for entry in entries:
        original = entry.get('grammar')
        core, modifier = split_grammar(original)
        
        if original not in grammar_stats:
            grammar_stats[original] = {
                'count': 0,
                'core': core,
                'modifier': modifier,
                'sample_ids': []
            }
        
        grammar_stats[original]['count'] += 1
        if len(grammar_stats[original]['sample_ids']) < 3:
            grammar_stats[original]['sample_ids'].append(str(entry['_id']))
    
    # Display analysis
    print(f"\n📈 Analysis of {len(entries):,} entries:")
    print(f"   Unique grammar types: {len(grammar_stats)}")
    print()
    
    # Group by whether they need splitting
    needs_splitting = {}
    no_change = {}
    
    for original, stats in grammar_stats.items():
        if stats['modifier'] is not None:
            needs_splitting[original] = stats
        else:
            no_change[original] = stats
    
    print(f"✂️  Types that will be split: {len(needs_splitting)}")
    print(f"✓  Types with no modifier: {len(no_change)}")
    
    # Show preview of changes
    print("\n" + "-" * 80)
    print("PREVIEW OF CHANGES (top 30 by count)")
    print("-" * 80)
    print(f"{'Original Grammar':<40} {'→ Core':<20} {'Modifier':<30} {'Count':>8}")
    print("-" * 80)
    
    sorted_changes = sorted(needs_splitting.items(), key=lambda x: -x[1]['count'])
    for original, stats in sorted_changes[:30]:
        core = stats['core'] or 'NULL'
        modifier = stats['modifier'] or ''
        print(f"{original:<40} → {core:<20} {modifier:<30} {stats['count']:>8,}")
    
    if len(sorted_changes) > 30:
        remaining = sum(s['count'] for o, s in sorted_changes[30:])
        print(f"{'... and more':<40} {'':20} {'':30} {remaining:>8,}")
    
    # Show types that won't change
    print("\n" + "-" * 80)
    print("TYPES WITH NO MODIFIER (top 10)")
    print("-" * 80)
    for original, stats in sorted(no_change.items(), key=lambda x: -x[1]['count'])[:10]:
        display_name = original if original is not None else '[NULL]'
        print(f"  {display_name:<40} ({stats['count']:,} entries)")
    
    if dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN COMPLETE - No changes made")
        print("=" * 80)
        print("\nTo apply these changes, run:")
        print("  ./venv/bin/python scripts/split_grammar_types.py --apply")
        return
    
    # PHASE 2: Apply changes
    print("\n" + "-" * 80)
    print("PHASE 2: Applying changes to database")
    print("-" * 80)
    
    success_count = 0
    error_count = 0
    rate_limit_delays = 0
    
    print(f"\nProcessing {len(entries):,} entries with rate limiting...")
    print("  Strategy: 200ms delay after each update to avoid 429 errors")
    
    for i, entry in enumerate(entries, 1):
        original_grammar = entry.get('grammar')
        core, modifier = split_grammar(original_grammar)
        
        # Update the entry
        update_data = {
            'grammar': core,
            'grammar_modifier': modifier
        }
        
        retry_count = 0
        max_retries = 3
        
        while retry_count <= max_retries:
            try:
                db.dictionary_collection.update_one(
                    {'_id': entry['_id']},
                    {'$set': update_data}
                )
                success_count += 1
                break  # Success, exit retry loop
                
            except Exception as e:
                error_str = str(e)
                if '16500' in error_str or 'TooManyRequests' in error_str or '429' in error_str:
                    # Rate limited - use exponential backoff
                    retry_count += 1
                    rate_limit_delays += 1
                    
                    if retry_count <= max_retries:
                        wait_time = 2 ** retry_count  # 2, 4, 8 seconds
                        print(f"\n  ⏳ Rate limited at entry {i}, retry {retry_count}/{max_retries}, waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"  ❌ Failed after {max_retries} retries for entry {entry['_id']}")
                        error_count += 1
                        break
                else:
                    print(f"  ❌ Error updating entry {entry['_id']}: {e}")
                    error_count += 1
                    break
        
        # Progress indicator every 50 entries
        if i % 50 == 0:
            print(f"  Processed {i:,}/{len(entries):,} ({i*100//len(entries)}%) - "
                  f"Success: {success_count:,}, Errors: {error_count}, "
                  f"Rate limit delays: {rate_limit_delays}")
        
        # Consistent delay after each update to avoid rate limits (200ms)
        # This gives us ~5 updates/second, well within Cosmos DB free tier limits
        time.sleep(0.2)
    
    # Final summary
    print("\n" + "=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print(f"✓ Successfully updated: {success_count:,} entries")
    print(f"❌ Errors: {error_count}")
    print(f"⏳ Rate limit delays: {rate_limit_delays}")
    print(f"📊 Total processed: {len(entries):,}")
    
    # Verify results
    print("\n" + "-" * 80)
    print("VERIFICATION: New grammar field distribution")
    print("-" * 80)
    
    try:
        pipeline = [
            {'$match': {'grammar': {'$exists': True, '$ne': None}}},
            {'$group': {
                '_id': '$grammar',
                'count': {'$sum': 1}
            }},
            {'$sort': {'count': -1}},
            {'$limit': 20}
        ]
        
        results = list(db.dictionary_collection.aggregate(pipeline))
        print(f"{'Core Grammar':<30} {'Count':>10}")
        print("-" * 80)
        for r in results:
            print(f"{r['_id']:<30} {r['count']:>10,}")
        
    except Exception as e:
        print(f"⚠️  Could not verify results: {e}")
    
    print("\n" + "=" * 80)
    print("✓ Migration successful!")
    print("=" * 80)


def show_sample_entries(limit: int = 20):
    """Show sample entries with their split grammar."""
    db = DictionaryDB()
    
    if not db.client:
        print("❌ Failed to connect to database")
        return
    
    print("\n" + "=" * 80)
    print(f"SAMPLE ENTRIES WITH SPLIT GRAMMAR (showing {limit})")
    print("=" * 80)
    
    entries = list(db.dictionary_collection.find(
        {'grammar': {'$exists': True, '$ne': None}},
        {'chuukese_word': 1, 'english_translation': 1, 'grammar': 1, 'grammar_modifier': 1}
    ).limit(limit))
    
    print(f"\n{'Word':<20} {'English':<25} {'Core':<15} {'Modifier':<25}")
    print("-" * 85)
    
    for entry in entries:
        word = entry.get('chuukese_word', '')[:19]
        english = entry.get('english_translation', '')[:24]
        core = entry.get('grammar', '')[:14]
        modifier = entry.get('grammar_modifier', '') or ''
        modifier = modifier[:24]
        print(f"{word:<20} {english:<25} {core:<15} {modifier:<25}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Split grammar types into core + modifier',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes (dry run)
  ./venv/bin/python scripts/split_grammar_types.py
  
  # Apply changes to database
  ./venv/bin/python scripts/split_grammar_types.py --apply
  
  # Test with limited entries
  ./venv/bin/python scripts/split_grammar_types.py --apply --limit 100
  
  # Show sample entries after migration
  ./venv/bin/python scripts/split_grammar_types.py --samples
        """
    )
    
    parser.add_argument('--apply', action='store_true', 
                       help='Apply changes to database (default is dry run)')
    parser.add_argument('--limit', type=int, 
                       help='Limit number of entries to process (for testing)')
    parser.add_argument('--yes', action='store_true',
                       help='Skip confirmation prompt (use with caution!)')
    parser.add_argument('--samples', action='store_true',
                       help='Show sample entries with split grammar')
    
    args = parser.parse_args()
    
    if args.samples:
        show_sample_entries(limit=30)
    else:
        migrate_grammar_types(dry_run=not args.apply, max_entries=args.limit, skip_confirm=args.yes)
