"""
Enrich dictionary word entries with scripture references from the Chuukese NWT EPUB.
For each word entry, searches the EPUB for verses containing that word and stores
the scripture references in the 'references' field.
"""
import sys
import os
import re
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.search_epub_words import extract_all_verses, search_word_in_verses

# Database connection
from src.database.dictionary_db import DictionaryDB

EPUB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'config', 'data', 'bible', 'nwt_TE.epub')

# Max references to store per word (avoid huge fields)
MAX_REFS_PER_WORD = 20


def main():
    # Load EPUB verses once
    print(f"📖 Loading Chuukese NWT EPUB...")
    verses, book_map = extract_all_verses(EPUB_PATH)
    print(f"✅ Extracted {len(verses)} verses from {len(book_map)} books\n")

    # Connect to database
    db = DictionaryDB()
    collection = db.dictionary_collection

    # Get all word entries that don't already have references
    word_filter = {'type': 'word', '$or': [
        {'references': {'$exists': False}},
        {'references': ''},
        {'references': None}
    ]}
    total = collection.count_documents(word_filter)
    total_all = collection.count_documents({'type': 'word'})
    print(f"📊 {total_all} total word entries, {total} still need references\n")

    updated = 0
    skipped = 0
    no_match = 0
    errors = 0

    # Process in cursor batches
    cursor = collection.find(word_filter, {'_id': 1, 'chuukese_word': 1, 'references': 1})

    batch_updates = []
    processed = 0

    for entry in cursor:
        processed += 1
        word = entry.get('chuukese_word', '').strip()
        entry_id = entry['_id']

        if not word:
            skipped += 1
            continue

        # Skip very short words (1-2 chars) - too many false matches
        if len(word) <= 2:
            skipped += 1
            continue

        # Search for this word in all verses
        results = search_word_in_verses(verses, book_map, word)

        if not results:
            no_match += 1
            if processed % 500 == 0:
                print(f"  [{processed}/{total}] No scriptures for '{word}'")
            continue

        # Build references string (e.g., "Galatians 5:20, Philippians 2:3")
        # Use English book names for consistency
        from scripts.search_epub_words import BOOK_NAMES
        ref_strings = []
        for r in results[:MAX_REFS_PER_WORD]:
            eng_name = BOOK_NAMES.get(r['book_num'], f"Book {r['book_num']}")
            ref_strings.append(f"{eng_name} {r['chapter']}:{r['verse']}")

        refs_text = ', '.join(ref_strings)
        if len(results) > MAX_REFS_PER_WORD:
            refs_text += f" (+{len(results) - MAX_REFS_PER_WORD} more)"

        batch_updates.append({
            '_id': entry_id,
            'references': refs_text,
            'word': word,
            'count': len(results)
        })

        # Apply batch updates every 10 entries
        if len(batch_updates) >= 10:
            applied = apply_updates(collection, batch_updates)
            updated += applied
            errors += len(batch_updates) - applied
            batch_updates = []
            print(f"  [{processed}/{total}] Updated {updated} entries so far...")
            time.sleep(1)  # Rate limit pause

    # Apply remaining updates
    if batch_updates:
        applied = apply_updates(collection, batch_updates)
        updated += applied
        errors += len(batch_updates) - applied

    print(f"\n{'='*60}")
    print(f"✅ Done! Processed {processed} word entries")
    print(f"   Updated: {updated}")
    print(f"   No matches: {no_match}")
    print(f"   Skipped (short/empty): {skipped}")
    print(f"   Errors: {errors}")


def apply_updates(collection, batch_updates):
    """Apply a batch of reference updates with rate-limit retry."""
    applied = 0
    for item in batch_updates:
        retries = 3
        while retries > 0:
            try:
                collection.update_one(
                    {'_id': item['_id']},
                    {'$set': {'references': item['references']}}
                )
                applied += 1
                break
            except Exception as e:
                if '16500' in str(e) or 'RetryAfterMs' in str(e):
                    retries -= 1
                    retry_match = re.search(r'RetryAfterMs=(\d+)', str(e))
                    delay = int(retry_match.group(1)) / 1000.0 if retry_match else 2.0
                    time.sleep(delay)
                else:
                    print(f"  ❌ Error updating '{item['word']}': {e}")
                    break
    return applied


if __name__ == '__main__':
    main()
