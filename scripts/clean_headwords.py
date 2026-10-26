#!/usr/bin/env python
"""
Strip stray punctuation from headwords the Translation Game saved.

    python scripts/clean_headwords.py            # report only, writes data/dedupe/headword_report.json
    python scripts/clean_headwords.py --apply    # rename, merging into a clean entry where one exists

Word pairs saved from the game used to keep the punctuation attached to the
word in the article, so the dictionary holds rows such as "Jeremaia," and
"“ewe" beside (or instead of) "Jeremaia" and "ewe". Those rows never match the
word again. Only rows the game wrote (source "translation_game_word_pair") are
touched: imported entries use punctuation deliberately ("alolileniuk*",
"(1 min.)") and stored example sentences keep their commas. For each game row:

* if a clean entry already exists, the copies are merged with the same rules
  as scripts/dedupe_dictionary.py (senses combined, longest definition kept,
  history recorded on the survivor) and the punctuated copies deleted;
* otherwise the headword is simply rewritten in its clean form.

The English side of every game row gets the same treatment ("(1 min." ->
"1 min", "Moab; “Moab”" -> "Moab"), since the old save code only trimmed
trailing punctuation from English words.

Rows from other sources whose headword carries outer punctuation are counted
in the report for information only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.dictionary_merge import clean_headword, clean_senses, merge_group  # noqa: E402
from src.database.dictionary_db import DictionaryDB  # noqa: E402

REPORT = Path(__file__).resolve().parents[1] / "data" / "dedupe" / "headword_report.json"
SOURCES = (("dictionary_collection", "chuukese_word"), ("phrases_collection", "chuukese_phrase"), ("words_collection", "chuukese"))
GAME_SOURCES = {"translation_game_word_pair"}


def from_game(doc: dict) -> bool:
    return (doc.get("source") or "") in GAME_SOURCES


def retry(fn, attempts: int = 8):
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


def plan_collection(col, field: str) -> list[dict]:
    """What to do in one collection: a `rename` for a punctuated row with no
    clean twin, a `merge` when a clean twin exists."""
    by_clean: dict[str, list[dict]] = defaultdict(list)
    dirty_keys: set[str] = set()
    other_dirty = 0
    for doc in col.find({}, {field: 1, "english_translation": 1, "grammar": 1, "grammar_modifier": 1, "definition": 1, "references": 1, "source": 1}):
        raw = str(doc.get(field) or "")
        clean = clean_headword(raw)
        if not clean:
            continue
        by_clean[clean.lower()].append(doc)
        if clean != raw.strip():
            if from_game(doc):
                dirty_keys.add(clean.lower())
            else:
                other_dirty += 1
    if other_dirty:
        print(f"   ({other_dirty} rows from other sources carry punctuation and are left alone)")

    plan = []
    # English wordings of game rows whose headword is already clean.
    for key, rows in sorted(by_clean.items()):
        if key in dirty_keys:
            continue
        for d in rows:
            english = str(d.get("english_translation") or "")
            if from_game(d) and english and clean_senses(english) != english.strip():
                plan.append({"action": "english", "id": str(d["_id"]), "headword": d.get(field), "from": english, "to": clean_senses(english)})
    for key in sorted(dirty_keys):
        rows = by_clean[key]
        dirty = [d for d in rows if from_game(d) and clean_headword(d.get(field)) != str(d.get(field) or "").strip()]
        clean_rows = [d for d in rows if d not in dirty and clean_headword(d.get(field)) == str(d.get(field) or "").strip()]
        rows = clean_rows + dirty
        # The stored spelling: a clean row's own if there is one, else the cleaned form.
        headword = str(clean_rows[0][field]).strip() if clean_rows else clean_headword(dirty[0][field])
        if len(rows) == 1:
            english = str(dirty[0].get("english_translation") or "")
            plan.append({"action": "rename", "id": str(dirty[0]["_id"]), "from": dirty[0][field], "to": headword,
                         "english_from": english, "english_to": clean_senses(english)})
            continue
        result = merge_group(rows)
        # A clean row should survive when there is one; merge_group picks the
        # best-populated, so re-point when it chose a punctuated copy.
        survivor = result["survivor"]
        if clean_rows and survivor in dirty:
            survivor = max(clean_rows, key=lambda d: str(d.get("english_translation") or ""))
            result = merge_group([survivor] + [d for d in rows if d is not survivor])
            result["survivor"] = survivor
        update = dict(result["update"])
        english = str(update.get("english_translation", result["survivor"].get("english_translation")) or "")
        if clean_senses(english) != english.strip():
            update["english_translation"] = clean_senses(english)
        plan.append(
            {
                "action": "merge",
                "survivor": str(result["survivor"]["_id"]),
                "to": headword,
                "absorbed": [str(i) for i in result["absorbed"]],
                "update": update,
                "grammar_conflict": result["grammar_conflict"],
                "copies": [
                    {"id": str(d["_id"]), "headword": d.get(field), "english": d.get("english_translation"), "grammar": d.get("grammar"), "definition": d.get("definition")}
                    for d in rows
                ],
            }
        )
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the renames and merges")
    args = ap.parse_args()

    db = DictionaryDB()
    plans: dict[str, list[dict]] = {}
    tally: Counter = Counter()
    for attr, field in SOURCES:
        col = getattr(db, attr, None)
        if col is None:
            continue
        plan = plan_collection(col, field)
        plans[attr] = plan
        for item in plan:
            tally[item["action"]] += 1
            if item["action"] == "merge":
                tally["absorbed"] += len(item["absorbed"])
        print(f"{attr}: {sum(1 for p in plan if p['action'] == 'rename')} to rename, {sum(1 for p in plan if p['action'] == 'merge')} to merge into a clean entry")
        for item in plan[:25]:
            if item["action"] == "rename":
                extra = f"  (english {item['english_from']!r} -> {item['english_to']!r})" if item["english_from"] != item["english_to"] else ""
                print(f"   rename  {item['from']!r} -> {item['to']!r}{extra}")
            elif item["action"] == "english":
                print(f"   english {item['headword']!r}: {item['from']!r} -> {item['to']!r}")
            else:
                print(f"   merge   {[c['headword'] for c in item['copies']]} -> {item['to']!r}")
        if len(plan) > 25:
            print(f"   … {len(plan) - 25} more in the report")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(), "tally": dict(tally), "plans": plans}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\nrenames {tally['rename']}, english cleanups {tally['english']}, merges {tally['merge']} (copies removed {tally['absorbed']})")
    print(f"report: {REPORT}")
    if not args.apply:
        print("\nReport only. Re-run with --apply to write.")
        return 0

    now = datetime.now(timezone.utc)
    from bson import ObjectId

    def oid(value):
        try:
            return ObjectId(value)
        except Exception:
            return value

    done = 0
    for attr, field in SOURCES:
        col = getattr(db, attr, None)
        for item in plans.get(attr, []):
            if item["action"] == "rename":
                before, after = {field: item["from"]}, {field: item["to"]}
                if item["english_from"] != item["english_to"]:
                    before["english_translation"], after["english_translation"] = item["english_from"], item["english_to"]
                history = {"at": now, "by": "clean_headwords.py", "kind": "rename", "before": before, "after": after}
                retry(lambda: col.update_one({"_id": oid(item["id"])}, {"$set": {**after, "date_modified": now}, "$push": {"history": history}}))
            elif item["action"] == "english":
                history = {"at": now, "by": "clean_headwords.py", "kind": "clean_english", "before": {"english_translation": item["from"]}, "after": {"english_translation": item["to"]}}
                retry(lambda: col.update_one({"_id": oid(item["id"])}, {"$set": {"english_translation": item["to"], "date_modified": now}, "$push": {"history": history}}))
            else:
                update = dict(item["update"])
                update.update({field: item["to"], "merged_from": item["absorbed"], "date_modified": now})
                history = {
                    "at": now,
                    "by": "clean_headwords.py",
                    "kind": "merge",
                    "merged_from": item["absorbed"],
                    "after": item["update"],
                    "absorbed_copies": [c for c in item["copies"] if c["id"] != item["survivor"]],
                }
                retry(lambda: col.update_one({"_id": oid(item["survivor"])}, {"$set": update, "$push": {"history": history}}))
                retry(lambda: col.delete_many({"_id": {"$in": [oid(i) for i in item["absorbed"]]}}))
            done += 1
            time.sleep(0.05)
    print(f"\napplied {done} changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
