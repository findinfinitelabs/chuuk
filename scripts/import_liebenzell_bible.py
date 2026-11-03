#!/usr/bin/env python3
"""
Import the Liebenzell Mission Chuukese Bible (Genesis–Malachi) from its PDF
into data/bible/liebenzell_chk_ot.json and the Cosmos `bible_chapters`
collection (lang "chk_lm"), for the Talk Builder's Hebrew Scriptures fallback.

    .venv/bin/python scripts/import_liebenzell_bible.py ~/Downloads/chk_all.pdf [--no-db]
"""
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core import liebenzell_bible as lb  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--no-db", action="store_true")
    args = ap.parse_args()
    bible = lb.parse_pdf(args.pdf, books=range(1, 40))
    lb.save(bible)
    chapters = sum(len(c) for c in bible.values())
    verses = sum(len(v) for c in bible.values() for v in c.values())
    print(f"parsed {len(bible)} books, {chapters} chapters, {verses} verses → {lb.DATA_FILE}")
    if args.no_db:
        return
    from dotenv import load_dotenv
    from src.database.db_factory import get_cosmos_client

    load_dotenv()
    col = get_cosmos_client()["chuuk_dictionary"][lb.COLLECTION]
    n = 0
    for book, chs in sorted(bible.items()):
        for chapter, vs in sorted(chs.items()):
            doc = {"lang": lb.LANG, "book": book, "chapter": chapter, "verses": {str(v): t for v, t in sorted(vs.items())}, "source": lb.SOURCE, "fetched_at": datetime.now(timezone.utc)}
            for attempt in range(6):
                try:
                    col.update_one({"lang": lb.LANG, "book": book, "chapter": chapter}, {"$set": doc}, upsert=True)
                    break
                except Exception as e:  # Cosmos 429
                    time.sleep(1.5 * (attempt + 1))
                    if attempt == 5:
                        raise e
            n += 1
            time.sleep(0.08)
    print(f"upserted {n} chapters into {lb.COLLECTION} (lang {lb.LANG})")


if __name__ == "__main__":
    main()
