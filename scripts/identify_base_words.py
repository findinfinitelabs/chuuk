#!/usr/bin/env python3
"""
Script to identify and mark base words in the dictionary database.
Base words are the root/uninflected forms without suffixes or modifications.
"""

import sys
import time
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')

from src.database.dictionary_db import DictionaryDB

# Grammar types that indicate NOT a base word (has modifications)
NON_BASE_GRAMMAR = [
    'noun + possessive',
    'noun + suffix',
    'noun + pronoun',
    'verb + suffix',
    'verb + directional',
    'verb + pronoun suffix',
    'verb + pronoun',
    'transitive verb + suffix',
    'transitive verb + pronoun suffix',
    'transitive verb + pronoun',
    'transitive verb + directional',
    'adjective + suffix',
    'preposition + suffix',
    'preposition + possessive',
    'possessed form',
    'possessed locational',
    'locational noun + possessive',
    'temporal noun + possessive',
    'possessive',
    'possessive suffix',
    'stand-alone possessive',
    'preposition + possessive suffix'
]

# Grammar types that typically indicate base words
BASE_GRAMMAR = [
    'noun',
    'verb',
    'transitive verb',
    'intransitive verb',
    'adjective',
    'adverb',
    'pronoun',
    'preposition',
    'conjunction',
    'particle',
    'auxiliary',
    'classifier',
    'numeral',
    'ordinal',
    'demonstrative',
    'interjection',
    'quantifier',
    'interrogative',
    'article',
    'locational noun',
    'relational noun',
    'temporal noun'
]

def is_base_word(entry):
    """
    Determine if an entry represents a base word.
    """
    grammar = entry.get('grammar', '')
    inflection_type = entry.get('inflection_type', '')
    word = entry.get('chuukese_word', '')
    
    # If it has inflection_type, it's not a base word
    if inflection_type and inflection_type != 'base':
        return False
    
    # If grammar indicates modified form, not a base word
    if grammar in NON_BASE_GRAMMAR:
        return False
    
    # If grammar indicates base form, it's a base word
    if grammar in BASE_GRAMMAR:
        return True
    
    # For reduplicated forms, consider them base if they're the main entry
    if 'reduplicated' in grammar.lower():
        return True
    
    # Default: if single word with base-type grammar or no special markers
    if ' ' not in word.strip():
        return True
    
    return False

def identify_and_mark_base_words(dry_run=True):
    """
    Identify base words and mark them in the database.
    """
    db = DictionaryDB()
    
    if not db.client:
        print("Failed to connect to database")
        return
    
    print("Analyzing dictionary entries to identify base words...")
    print("=" * 70)
    
    # Get all entries
    all_entries = list(db.dictionary_collection.find({}))
    total = len(all_entries)
    
    base_count = 0
    non_base_count = 0
    updated_count = 0
    
    print(f"Total entries: {total}")
    print()
    
    # Track examples
    base_examples = []
    non_base_examples = []
    
    for entry in all_entries:
        is_base = is_base_word(entry)
        current_value = entry.get('is_base_word')
        
        if is_base:
            base_count += 1
            if len(base_examples) < 10:
                base_examples.append({
                    'word': entry.get('chuukese_word', ''),
                    'grammar': entry.get('grammar', ''),
                    'english': entry.get('english_translation', '')
                })
        else:
            non_base_count += 1
            if len(non_base_examples) < 10:
                non_base_examples.append({
                    'word': entry.get('chuukese_word', ''),
                    'grammar': entry.get('grammar', ''),
                    'english': entry.get('english_translation', '')
                })
        
        # Update if needed
        if current_value != is_base:
            if not dry_run:
                try:
                    db.dictionary_collection.update_one(
                        {'_id': entry['_id']},
                        {'$set': {'is_base_word': is_base}}
                    )
                    updated_count += 1
                    
                    # Rate limiting
                    if updated_count % 50 == 0:
                        time.sleep(0.1)
                        
                except Exception as e:
                    if '16500' in str(e):
                        print(f"Rate limited, waiting...")
                        time.sleep(1)
                        try:
                            db.dictionary_collection.update_one(
                                {'_id': entry['_id']},
                                {'$set': {'is_base_word': is_base}}
                            )
                            updated_count += 1
                        except Exception as e2:
                            print(f"Failed to update entry: {e2}")
                    else:
                        print(f"Failed to update entry: {e}")
            else:
                updated_count += 1
    
    print(f"Base words: {base_count} ({base_count/total*100:.1f}%)")
    print(f"Non-base words: {non_base_count} ({non_base_count/total*100:.1f}%)")
    print(f"Entries to update: {updated_count}")
    print()
    
    print("Example BASE WORDS (will be shown in dark purple, bold):")
    print("-" * 70)
    for ex in base_examples:
        grammar = f" ({ex['grammar']})" if ex['grammar'] else ""
        print(f"  • {ex['word']}{grammar} = {ex['english']}")
    
    print()
    print("Example NON-BASE WORDS (regular display):")
    print("-" * 70)
    for ex in non_base_examples:
        grammar = f" ({ex['grammar']})" if ex['grammar'] else ""
        print(f"  • {ex['word']}{grammar} = {ex['english']}")
    
    if dry_run:
        print()
        print("[DRY RUN] No changes made. Run with --apply to update the database.")
    else:
        print()
        print(f"✓ Updated {updated_count} entries in the database.")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Identify and mark base words in dictionary')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry run)')
    args = parser.parse_args()
    
    identify_and_mark_base_words(dry_run=not args.apply)
