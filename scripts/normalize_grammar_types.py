#!/usr/bin/env python3
"""
Script to normalize grammar types in the dictionary database.
Consolidates duplicate/similar grammar types into standardized forms.
"""

import sys
import time
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')

from src.database.dictionary_db import DictionaryDB

# Mapping of old grammar types to normalized forms
GRAMMAR_NORMALIZATION = {
    # Verb reduplicated variations
    'v. (redup.)': 'verb (reduplicated)',
    'v (redup)': 'verb (reduplicated)',
    'v (redup.)': 'verb (reduplicated)',
    'v. (reduplicated)': 'verb (reduplicated)',
    'verb (redup.)': 'verb (reduplicated)',
    'verb, reduplicated': 'verb (reduplicated)',
    'verb (intensive reduplicated)': 'verb (reduplicated)',
    
    # Adjective reduplicated
    'adj. (redup.)': 'adjective (reduplicated)',
    
    # Noun + possessive variations
    'noun + poss': 'noun + possessive',
    'noun + possessive suffix': 'noun + possessive',
    'noun with possessive suffix': 'noun + possessive',
    'noun (possessed)': 'noun + possessive',
    'possessed noun': 'noun + possessive',
    
    # Verb + directional
    'verb + dir': 'verb + directional',
    
    # Transitive verb + pronoun suffix variations
    'transitive verb with pronoun suffix': 'transitive verb + pronoun suffix',
    'transitive verb + object suffix': 'transitive verb + pronoun suffix',
    'verb + obj suffix': 'verb + pronoun suffix',
    
    # Classifier variations
    'classifier (counting word)': 'classifier',
    'classifier (possessed)': 'classifier',
    'numeral classifier': 'classifier',
    
    # Combined types - simplify to primary
    'verb, transitive verb': 'transitive verb',
    'verb, transitive verb + suffix': 'transitive verb + suffix',
    'adjective, noun': 'adjective',
    'adjective, ordinal': 'ordinal',
    'noun, verb': 'noun',
    'noun, intransitive verb': 'noun',
    'verb / noun': 'verb',
    'verb / stative': 'verb',
    'adjective / verb': 'adjective',
    'adjective / adverb': 'adverb',
    'adverb / quantifier': 'adverb',
    'n. / vt': 'noun',
    'adv./v': 'adverb',
    'v./adj': 'verb',
    'verb/adj': 'verb',
    'noun/verb': 'noun',
    'adj./vt + poss': 'adjective',
    'adj./mod': 'adjective',
    
    # Particle variations
    'negative particle': 'particle',
    'emphatic particle': 'particle',
    'negative auxiliary': 'auxiliary',
    'particle/copula': 'particle',
    'particle / copula': 'particle',
    
    # Demonstrative variations
    'demonstrative plural': 'demonstrative',
    'demonstrative noun': 'demonstrative',
    
    # Locational variations
    'locationals': 'locational noun',
    'locational': 'locational noun',
    
    # Temporal
    'negative temporal': 'adverb',
    
    # Relational variations
    'relational': 'relational noun',
    
    # Phrase types (not grammar)
    'phrase': None,  # Remove - not a grammar type
    'pronoun phrase': None,
    'example phrase': None,
    'prep/phrase': 'preposition',
    'adv/phrase': 'adverb',
    
    # Other
    '—': None,  # Remove invalid
    'unknown': None,  # Remove unknown
    'intr': 'intransitive verb',
    'noun form': 'noun',
    'existential': 'verb',
    'pronoun suffix': 'pronoun',
}


def normalize_grammar_types(dry_run=True):
    """Normalize grammar types in the database."""
    db = DictionaryDB()
    
    if not db.client:
        print("Failed to connect to database")
        return
    
    total_updated = 0
    
    for old_grammar, new_grammar in GRAMMAR_NORMALIZATION.items():
        # Find entries with the old grammar type
        entries = list(db.dictionary_collection.find({'grammar': old_grammar}))
        count = len(entries)
        
        if count > 0:
            if new_grammar is None:
                action = f"REMOVE grammar field"
            else:
                action = f"→ '{new_grammar}'"
            
            print(f"  '{old_grammar}' ({count} entries) {action}")
            
            if not dry_run:
                # Update one at a time to avoid rate limits
                updated = 0
                for entry in entries:
                    try:
                        if new_grammar is None:
                            db.dictionary_collection.update_one(
                                {'_id': entry['_id']},
                                {'$unset': {'grammar': ''}}
                            )
                        else:
                            db.dictionary_collection.update_one(
                                {'_id': entry['_id']},
                                {'$set': {'grammar': new_grammar}}
                            )
                        updated += 1
                    except Exception as e:
                        if '16500' in str(e):
                            # Rate limited - wait and retry
                            time.sleep(0.5)
                            try:
                                if new_grammar is None:
                                    db.dictionary_collection.update_one(
                                        {'_id': entry['_id']},
                                        {'$unset': {'grammar': ''}}
                                    )
                                else:
                                    db.dictionary_collection.update_one(
                                        {'_id': entry['_id']},
                                        {'$set': {'grammar': new_grammar}}
                                    )
                                updated += 1
                            except Exception as e2:
                                print(f"    Failed to update entry: {e2}")
                        else:
                            print(f"    Failed to update entry: {e}")
                    
                    # Small delay to avoid rate limits
                    if count > 50:
                        time.sleep(0.05)
                
                total_updated += updated
                print(f"    Updated {updated}/{count}")
    
    if dry_run:
        print("\n[DRY RUN] No changes made. Run with --apply to make changes.")
    else:
        print(f"\nTotal updated: {total_updated} entries.")


def show_current_stats():
    """Show current grammar type distribution."""
    db = DictionaryDB()
    stats = db.get_stats()
    
    print("\nCurrent Grammar Types:")
    print("-" * 50)
    
    grammar_breakdown = stats.get('grammar_breakdown', {})
    for grammar, count in sorted(grammar_breakdown.items(), key=lambda x: -x[1]):
        print(f"  {grammar}: {count}")
    
    print(f"\nTotal unique grammar types: {len(grammar_breakdown)}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Normalize grammar types in dictionary')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry run)')
    parser.add_argument('--stats', action='store_true', help='Show current stats only')
    args = parser.parse_args()
    
    if args.stats:
        show_current_stats()
    else:
        print("Grammar Type Normalization")
        print("=" * 50)
        normalize_grammar_types(dry_run=not args.apply)
        
        if args.apply:
            print("\n" + "=" * 50)
            show_current_stats()
