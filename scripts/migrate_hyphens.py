"""
Migrate hyphenated dictionary entries:
  - Strip hyphen from chuukese_word (e.g., kosokos-ei → kosokosei)
  - Add morphological breakdown to definition (e.g., "kosokos + suffix -ei (1sg object)")
  - Preserve existing definition content
  - Mark edited_by: 'AI'

Usage:
  python scripts/migrate_hyphens.py --dry-run   # Preview changes (default)
  python scripts/migrate_hyphens.py --apply      # Apply changes to database
"""
import sys, os, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.dictionary_db import DictionaryDB
from datetime import datetime

# Known suffix classifications for Chuukese
SUFFIX_INFO = {
    # Object pronoun suffixes
    'ei':    '1sg object (me)',
    'ók':    '2sg object (you)',
    'uk':    '2sg object (you)',
    'kem':   '1pl excl object (us, excl.)',
    'kemi':  '2pl object (you all)',
    'kich':  '1pl incl object (us, incl.)',
    'er':    '3pl object (them)',
    'ir':    '3pl object (them)',
    'úr':    '3pl object (them)',
    'iir':   '3pl object (them)',

    # Directional suffixes
    'to':    'directional (toward speaker)',
    'oto':   'directional (toward speaker)',
    'ló':    'directional (away)',
    'óló':   'directional (away)',
    'tá':    'directional (upward)',
    'tiw':   'directional (downward)',
    'long':  'directional (inward)',
    'ólong': 'directional (inward)',
    'wu':    'directional (outward)',

    # Possessive suffixes
    'om':    'possessive (your, sg.)',
    'óm':    'possessive (your, sg.)',
    'úm':    'possessive (your, sg.)',
    'an':    'possessive (his/her/its)',
    'ach':   'possessive (our, excl.)',
    'emi':   'possessive (your, pl.)',
    'imi':   'possessive (your, pl.)',
    'em':    'possessive (our, incl.)',
    'im':    'possessive (our, incl.)',
    'um':    'possessive (our, incl.)',
    'ich':   'possessive (our, incl.)',

    # Locational / other
    'n':     'locational/construct suffix',
    'in':    'locational suffix',
    'i':     'transitive suffix',
}


def classify_suffix(suffix, existing_def):
    """Get a description for the suffix, using known map or existing definition."""
    # Clean suffix (remove trailing *)
    clean = suffix.rstrip('*')

    if clean in SUFFIX_INFO:
        return SUFFIX_INFO[clean]

    # Fall back to existing definition if it looks like a suffix description
    if existing_def:
        lower = existing_def.lower()
        # If existing definition already describes the suffix, use it
        for keyword in ['object', 'suffix', 'directional', 'possessive', 'locational',
                        '1sg', '2sg', '3sg', '1pl', '2pl', '3pl', 'excl', 'incl',
                        'transitive']:
            if keyword in lower:
                return existing_def
    return f'suffix'


def build_new_definition(original_word, base, suffix, existing_def):
    """Build the new definition with morphological info prepended."""
    suffix_desc = classify_suffix(suffix, existing_def)

    # Check if existing_def IS the suffix description (no actual meaning)
    existing_lower = (existing_def or '').lower().strip()
    is_only_suffix_desc = False
    for keyword in ['object suffix', 'directional suffix', 'directional form',
                    '1sg', '2sg', '3sg', '1pl', '2pl', '3pl',
                    'transitive', 'locational']:
        if existing_lower.startswith(keyword) or existing_lower == keyword:
            is_only_suffix_desc = True
            break

    # Morphological note
    morph_note = f'{base} + suffix -{suffix}'
    if suffix_desc != existing_def:
        morph_note += f' ({suffix_desc})'

    if is_only_suffix_desc or not existing_def:
        # Definition was just the suffix label - use the suffix description as the definition
        return morph_note
    else:
        # Prepend morphological note to existing definition
        return f'{morph_note}. {existing_def}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    args = parser.parse_args()

    apply = args.apply
    if not apply:
        print("=== DRY RUN MODE (use --apply to commit changes) ===\n")

    db = DictionaryDB()
    coll = db.dictionary_collection

    # Find all hyphenated word entries
    results = list(coll.find(
        {'type': 'word', 'chuukese_word': {'$regex': '-'}},
        {'chuukese_word': 1, 'english_translation': 1, 'definition': 1, 'grammar': 1, '_id': 1}
    ))
    print(f"Total hyphenated entries found: {len(results)}")

    # Separate single-hyphen vs multi-hyphen
    single_hyphen = []
    multi_hyphen = []
    for r in results:
        word = r['chuukese_word']
        parts = word.split('-')
        if len(parts) == 2:
            single_hyphen.append(r)
        else:
            multi_hyphen.append(r)

    print(f"  Single-hyphen entries: {len(single_hyphen)}")
    print(f"  Multi-hyphen entries: {len(multi_hyphen)} (skipped - need manual review)")
    print()

    if multi_hyphen:
        print("=== Multi-hyphen entries (skipped) ===")
        for r in multi_hyphen:
            print(f"  {r['chuukese_word']}")
        print()

    # Check for potential duplicates
    duplicate_count = 0
    updates = []

    for r in single_hyphen:
        word = r['chuukese_word']
        base, suffix = word.split('-', 1)
        new_word = base + suffix
        existing_def = r.get('definition', '') or ''
        english = r.get('english_translation', '') or ''

        new_def = build_new_definition(word, base, suffix, existing_def)

        # Check if un-hyphenated form already exists
        existing = coll.find_one({'type': 'word', 'chuukese_word': new_word, '_id': {'$ne': r['_id']}})
        if existing:
            duplicate_count += 1
            if not apply:
                print(f"  DUPLICATE: {word} → {new_word} already exists (will skip)")
            continue

        updates.append({
            '_id': r['_id'],
            'old_word': word,
            'new_word': new_word,
            'old_def': existing_def,
            'new_def': new_def,
            'english': english,
        })

    print(f"Entries to update: {len(updates)}")
    print(f"Duplicates skipped: {duplicate_count}")
    print()

    # Show preview
    preview_count = min(30, len(updates))
    print(f"=== Preview (first {preview_count} changes) ===")
    for u in updates[:preview_count]:
        print(f"  {u['old_word']:30s} → {u['new_word']}")
        print(f"    English: {u['english'][:60]}")
        print(f"    Old def: {u['old_def'][:70]}")
        print(f"    New def: {u['new_def'][:70]}")
        print()

    if not apply:
        print(f"\n=== DRY RUN COMPLETE. {len(updates)} entries would be updated. ===")
        print("Run with --apply to commit changes.")
        return

    # Apply changes in batches
    print(f"\n=== APPLYING {len(updates)} UPDATES ===")
    batch_size = 10
    success = 0
    errors = 0
    now = datetime.utcnow()

    for i, u in enumerate(updates):
        try:
            coll.update_one(
                {'_id': u['_id']},
                {'$set': {
                    'chuukese_word': u['new_word'],
                    'definition': u['new_def'],
                    'edited_by': 'AI',
                    'updated_date': now,
                }}
            )
            success += 1
        except Exception as e:
            errors += 1
            print(f"  ERROR updating {u['old_word']}: {e}")
            # Rate limit retry
            time.sleep(2)
            try:
                coll.update_one(
                    {'_id': u['_id']},
                    {'$set': {
                        'chuukese_word': u['new_word'],
                        'definition': u['new_def'],
                        'edited_by': 'AI',
                        'updated_date': now,
                    }}
                )
                success += 1
                errors -= 1
            except Exception as e2:
                print(f"  RETRY FAILED: {u['old_word']}: {e2}")

        # Rate limiting for Cosmos DB
        if (i + 1) % batch_size == 0:
            time.sleep(1)
            print(f"  Progress: {i + 1}/{len(updates)} ({success} ok, {errors} errors)")

    print(f"\n=== MIGRATION COMPLETE ===")
    print(f"  Updated: {success}")
    print(f"  Errors:  {errors}")
    print(f"  Skipped (duplicates): {duplicate_count}")
    print(f"  Skipped (multi-hyphen): {len(multi_hyphen)}")


if __name__ == '__main__':
    main()
