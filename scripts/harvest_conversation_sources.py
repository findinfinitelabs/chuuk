#!/usr/bin/env python3
"""
Fetch the publications the Conversation Builder draws on from wol.jw.org, in
Chuukese and English, parse them (src/core/conversation_sources) and store
them in the ``conversation_sources`` collection.

    .venv/bin/python scripts/harvest_conversation_sources.py            # lmd + workbook weeks
    .venv/bin/python scripts/harvest_conversation_sources.py --no-workbook
    .venv/bin/python scripts/harvest_conversation_sources.py --years 2026 2027

Every page goes through the polite fetcher (one request at a time, spaced,
cached under data/wol_cache, capped), so a rerun costs nothing for pages
already held. Workbook weeks are found through the Chuukese library index
(year page → issue pages → week documents), as the pair harvest does.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.harvest_wol_pairs import PoliteFetcher, discover, log  # noqa: E402
from src.core import conversation_sources as cs  # noqa: E402
from src.core.wol_search import WOL_BASE  # noqa: E402

DOC = {
    "chk": WOL_BASE + "/chk/wol/d/r303/lp-te/{doc_id}",
    "en": WOL_BASE + "/en/wol/d/r1/lp-e/{doc_id}",
}


def fetch_pair(fetcher: PoliteFetcher, doc_id: str) -> tuple[str | None, str | None]:
    chk = fetcher.get(DOC["chk"].format(doc_id=doc_id))
    if chk is None:
        return None, None
    en = fetcher.get(DOC["en"].format(doc_id=doc_id))
    return chk, en


def main() -> int:
    parser = argparse.ArgumentParser(description="Harvest Conversation Builder sources from wol.jw.org")
    parser.add_argument("--no-workbook", action="store_true")
    parser.add_argument("--no-lmd", action="store_true")
    parser.add_argument("--years", type=int, nargs="*", default=[datetime.now().year, datetime.now().year + 1])
    parser.add_argument("--max-weeks", type=int, default=80)
    parser.add_argument("--max-requests", type=int, default=250)
    parser.add_argument("--min-interval", type=float, default=3.0)
    parser.add_argument("--dry-run", action="store_true", help="Parse and report, do not write to the database")
    args = parser.parse_args()

    fetcher = PoliteFetcher(min_interval=args.min_interval, jitter=2.0, max_requests=args.max_requests)
    now = datetime.now(timezone.utc)
    records: list[dict] = []

    if not args.no_lmd:
        log("Love People—Make Disciples…")
        for n, doc_id in enumerate(cs.LMD["lessons"], start=1):
            chk, en = fetch_pair(fetcher, doc_id)
            if not (chk and en):
                log(f"   lesson {n}: missing")
                continue
            data = cs.parse_lesson(chk, en, n)
            records.append({"kind": "lesson", "doc_id": doc_id, "number": n, "data": data})
            log(f"   lesson {n}: {data['title']['en']} / {data['title']['chk']}")
        chk, en = fetch_pair(fetcher, cs.LMD["truths"])
        if chk and en:
            data = cs.parse_truths(chk, en)
            records.append({"kind": "truths", "doc_id": cs.LMD["truths"], "data": data})
            log(f"   truths: {len(data['subjects'])} subjects, {sum(len(s['statements']) for s in data['subjects'])} statements")
        chk, en = fetch_pair(fetcher, cs.LMD["end"])
        if chk and en:
            data = cs.parse_plain(chk, en)
            records.append({"kind": "end", "doc_id": cs.LMD["end"], "data": data})
            log(f"   end: {data['title']['en']} ({len(data['paragraphs'])} paragraphs)")

    if not args.no_workbook:
        for year in args.years:
            log(f"Workbook {year}…")
            try:
                docs = discover(fetcher, "mwb", year, [])
            except RuntimeError as e:
                log(f"   {e}")
                continue
            found = 0
            for doc_id, _issue, _title in docs[: args.max_weeks]:
                chk, en = fetch_pair(fetcher, doc_id)
                if not (chk and en):
                    continue
                data = cs.parse_workbook_week(chk, en, doc_id, year)
                if not data["parts"]:
                    continue  # issue cover pages and the like
                records.append({"kind": "workbook", "doc_id": doc_id, "year": year, "data": data})
                found += 1
            log(f"   {found} weeks")

    log(f"Fetched {fetcher.requests_made} pages, {fetcher.cache_hits} from cache; {len(records)} records")
    if args.dry_run:
        return 0

    from src.database.dictionary_db import DictionaryDB

    db = DictionaryDB()
    if db.db is None:
        log("❌ No database connection")
        return 1
    col = db.db["conversation_sources"]
    for r in records:
        col.update_one({"kind": r["kind"], "doc_id": r["doc_id"]}, {"$set": {**r, "fetched_at": now}}, upsert=True)
    log(f"Stored {len(records)} records in conversation_sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
