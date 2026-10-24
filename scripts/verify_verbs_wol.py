#!/usr/bin/env python
"""
Dry-run verification of dictionary verbs against wol.jw.org.

For each verb (most important first) this fetches real Chuukese sentences from
the Watchtower Online Library, lines each up with its English edition, and
judges the dictionary's translation against how WOL actually renders the word.
Grammar tags are checked for every entry. Nothing is written to the dictionary:
every finding becomes a row in the `translation_reviews` collection, which the
admin Review page accepts or rejects.

    python scripts/verify_verbs_wol.py --limit 500 --workers 3

Sentence pairs are cached in data/verb_verification/pairs.json so a rerun only
fetches verbs it has not seen.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.verb_verification import Baseline, grammar_proposal, rank_verbs, translation_proposal  # noqa: E402
from src.core.wol_search import WOLSearch  # noqa: E402
from src.database.dictionary_db import DictionaryDB  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "data" / "verb_verification" / "pairs.json"
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CACHE)


def corpus_counts(db) -> Counter:
    """Word counts from the Chuukese text already held locally."""
    counts: Counter = Counter()

    def add(text):
        for m in _WORD.finditer(text or ""):
            counts[m.group(0).lower()] += 1

    try:
        for doc in db.db["wol_searches"].find({}, {"results.text": 1}):
            for r in doc.get("results") or []:
                add(r.get("text"))
        for doc in db.db["game_articles"].find({}, {"chuukese_sentences.text": 1}):
            for s in doc.get("chuukese_sentences") or []:
                add(s.get("text"))
        for doc in db.db["brochure_matches"].find({}, {"chuukese_text": 1}):
            add(doc.get("chuukese_text"))
        for doc in db.db["article_analysis_paragraphs"].find({}, {"paragraph": 1}):
            add(str(doc.get("paragraph")))
    except Exception as e:  # frequency is a nicety for ordering only
        print(f"⚠️ corpus counts incomplete: {e}")
    return counts


def fetch_pairs(wol: WOLSearch, word: str, pages: int, hits: int) -> list[dict]:
    found = wol.search(word, pages=pages, limit=hits)
    results = found["results"]
    if not results:
        return []
    english = wol.english_for_many(results)
    pairs = []
    for hit, en in zip(results, english):
        if not en or en.get("scope") not in ("sentence", "verse"):
            continue
        form = next((s["text"].strip() for s in hit.get("segments", []) if s.get("match")), None)
        pairs.append(
            {
                "chk": hit["text"],
                "en": en["text"],
                "form": form,
                "link": hit.get("link"),
                "citation": hit.get("citation"),
                "title": hit.get("title"),
                "english_link": en.get("link"),
            }
        )
    return pairs


def retry_write(fn, attempts: int = 8):
    """Cosmos answers bursts of writes with 429 (code 16500); back off and retry."""
    from pymongo.errors import OperationFailure, WriteError

    delay = 0.5
    for attempt in range(attempts):
        try:
            return fn()
        except (WriteError, OperationFailure) as e:
            if getattr(e, "code", None) != 16500 or attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 10)


def upsert_review(col, run_id: str, entry: dict, proposal: dict, now) -> str:
    entry_id = str(entry["_id"])
    existing = retry_write(lambda: col.find_one({"entry_id": entry_id, "kind": proposal["kind"]}, {"status": 1}))
    time.sleep(0.03)  # stay under the provisioned request rate
    if existing and existing.get("status") in ("applied", "rejected", "accepted"):
        # A decision already taken stands; only the evidence is refreshed.
        retry_write(
            lambda: col.update_one(
                {"_id": existing["_id"]},
                {"$set": {"evidence": proposal["evidence"], "outcome": proposal["outcome"], "updated_at": now, "run_id": run_id}},
            )
        )
        return "kept"
    doc = {
        **proposal,
        "entry_id": entry_id,
        "headword": entry.get("chuukese_word"),
        "run_id": run_id,
        "updated_at": now,
    }
    retry_write(
        lambda: col.update_one(
            {"entry_id": entry_id, "kind": proposal["kind"]},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    )
    return proposal["outcome"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=500, help="how many verbs to check on WOL")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--pages", type=int, default=1, help="WOL result pages per verb")
    ap.add_argument("--hits", type=int, default=8, help="WOL hits to line up with English per verb")
    ap.add_argument("--skip-grammar", action="store_true", help="do not generate grammar proposals")
    ap.add_argument("--refetch", action="store_true", help="ignore the pair cache")
    args = ap.parse_args()

    db = DictionaryDB()
    col = db.dictionary_collection
    reviews = db.db["translation_reviews"]
    runs = db.db["review_runs"]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    now = datetime.now(timezone.utc)
    runs.insert_one({"_id": run_id, "started_at": now, "limit": args.limit, "status": "running"})

    fields = {"chuukese_word": 1, "english_translation": 1, "definition": 1, "grammar": 1, "grammar_modifier": 1, "base_word": 1}
    entries = list(col.find({}, fields))
    known = {(e.get("chuukese_word") or "").strip() for e in entries}
    for coll, field in ((db.phrases_collection, "chuukese_phrase"), (db.words_collection, "chuukese")):
        try:
            known.update((d.get(field) or "").strip() for d in coll.find({}, {field: 1}))
        except Exception:
            pass
    known.discard("")

    tally: Counter = Counter()

    # -- Grammar: every entry, no network --------------------------------------
    if not args.skip_grammar:
        for e in entries:
            prop = grammar_proposal(e, known)
            if prop:
                tally["grammar:" + upsert_review(reviews, run_id, e, prop, now)] += 1
        print(f"grammar proposals: {sum(v for k, v in tally.items() if k.startswith('grammar:'))}")

    # -- Translations: the most important verbs first -------------------------
    verbs = [e for e in entries if (e.get("grammar") or "").lower().startswith("verb")]
    single = [v for v in verbs if re.fullmatch(r"[^\W\d_]+", (v.get("chuukese_word") or "").strip())]
    ranked = rank_verbs(single, corpus_counts(db))[: args.limit]
    print(f"checking {len(ranked)} of {len(single)} single-word verbs on wol.jw.org")

    cache = {} if args.refetch else load_cache()
    lock = threading.Lock()
    wol = WOLSearch()
    todo = [v for v in ranked if v["chuukese_word"].strip() not in cache]
    started = time.time()

    def work(v):
        word = v["chuukese_word"].strip()
        try:
            return word, fetch_pairs(wol, word, args.pages, args.hits)
        except Exception as e:
            print(f"  ⚠️ {word}: {e}")
            return word, None

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(work, v) for v in todo]):
            word, pairs = future.result()
            done += 1
            if pairs is None:
                continue
            with lock:
                cache[word] = pairs
                if done % 10 == 0:
                    save_cache(cache)
                    rate = (time.time() - started) / done
                    print(f"  {done}/{len(todo)} fetched, {rate:.1f}s each, ~{(len(todo) - done) * rate / 60:.0f} min left")
    save_cache(cache)

    baseline = Baseline()
    for word in (v["chuukese_word"].strip() for v in ranked):
        for p in cache.get(word) or []:
            baseline.add(p["en"])

    for v in ranked:
        pairs = cache.get(v["chuukese_word"].strip()) or []
        prop = translation_proposal(v, pairs, baseline)
        tally["translation:" + upsert_review(reviews, run_id, v, prop, now)] += 1

    retry_write(lambda: runs.update_one(
        {"_id": run_id},
        {"$set": {"finished_at": datetime.now(timezone.utc), "status": "finished", "verbs_checked": len(ranked), "tally": dict(tally)}},
    ))
    print("\nrun", run_id)
    for k, n in sorted(tally.items()):
        print(f"  {n:5d}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
