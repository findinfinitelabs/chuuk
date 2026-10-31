#!/usr/bin/env python3
"""
One-time seed for the per-user library (src/api/user_library.py).

Before 2026-10-31 saved WOL searches, article analyses and sentence analyses
were one shared list. This files each existing document into a library:
the `created_by` user where the document records one, otherwise the owner
given with --default (the person who built the collection).

    .venv/bin/python scripts/seed_user_library.py --default chris.lundy@findinfinite.com
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SOURCES = (("article_analyses", "article"), ("wol_searches", "wol_search"), ("sentence_analyses", "sentence"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--default", required=True, help="Email that owns documents without created_by")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    from src.database.dictionary_db import DictionaryDB
    db = DictionaryDB()
    lib = db.db["user_library"]
    now = datetime.now(timezone.utc)
    for coll_name, kind in SOURCES:
        docs = list(db.db[coll_name].find({}, {"_id": 1, "created_by": 1}))
        time.sleep(0.3)
        owners = {}
        for d in docs:
            owners[(d.get("created_by") or args.default).strip().lower()] = owners.get((d.get("created_by") or args.default).strip().lower(), 0) + 1
        print(f"{coll_name}: {len(docs)} documents → {owners}")
        if not args.apply:
            continue
        for d in docs:
            email = (d.get("created_by") or args.default).strip().lower()
            lib.update_one({"user_email": email, "kind": kind, "item_id": d["_id"]},
                           {"$setOnInsert": {"saved_at": now}}, upsert=True)
            time.sleep(0.15)
        print(f"   linked {len(docs)}")
    if not args.apply:
        print("Dry run. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
