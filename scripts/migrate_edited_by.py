#!/usr/bin/env python3
"""
Migration: Set edited_by='MI' on all existing entries that lack the field.
Run once to backfill the new edited_by tracking field.
"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database.dictionary_db import DictionaryDB

BATCH = 10  # very small batches to stay under Cosmos 1000 RU/s while app is running


def _retry(fn, name, max_retries=8):
    """Retry a callable on Cosmos 16500 rate-limit errors."""
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if '16500' in str(e) or '429' in str(e):
                print(f"   ⏳ Rate-limited ({name}), waiting {delay:.1f}s")
                time.sleep(delay)
                delay = min(delay * 2, 15)
            else:
                raise
    raise RuntimeError(f"Exhausted retries for {name}")


def update_batch(coll, name):
    """Update up to BATCH docs missing edited_by. Returns count updated."""
    ids = _retry(
        lambda: [
            doc['_id']
            for doc in coll.find({'edited_by': {'$exists': False}}, {'_id': 1}).limit(BATCH)
        ],
        f"find-{name}"
    )
    if not ids:
        return 0

    result = _retry(
        lambda: coll.update_many(
            {'_id': {'$in': ids}},
            {'$set': {'edited_by': 'MI'}}
        ),
        f"update-{name}"
    )
    return result.modified_count


def migrate():
    db = DictionaryDB()

    collections = [
        ('dictionary_entries (words)', db.dictionary_collection),
        ('phrases', db.phrases_collection),
        ('paragraphs', db.paragraphs_collection),
    ]

    total_updated = 0
    for name, coll in collections:
        if coll is None:
            print(f"⚠️  Skipping {name} — collection not initialised")
            continue

        missing = _retry(
            lambda: coll.count_documents({'edited_by': {'$exists': False}}),
            f"count-{name}"
        )
        print(f"📦 {name}: {missing} entries missing edited_by")

        coll_updated = 0
        while True:
            n = update_batch(coll, name)
            if n == 0:
                break
            coll_updated += n
            if coll_updated % 200 == 0 or coll_updated == missing:
                print(f"   ✓ {coll_updated}/{missing} updated")
            time.sleep(2)  # longer pause between batches to share RU budget with app

        print(f"   ✅ {name}: {coll_updated} entries updated")
        total_updated += coll_updated

    print(f"\n🏁 Done — {total_updated} total entries updated to 'MI'")


if __name__ == '__main__':
    migrate()
