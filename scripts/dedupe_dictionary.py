#!/usr/bin/env python
"""
Collapse duplicate dictionary entries (same headword) into one.

    python scripts/dedupe_dictionary.py            # report only, writes data/dedupe/report.json
    python scripts/dedupe_dictionary.py --apply    # merge and delete the absorbed copies

For each headword with several entries the best-populated copy survives;
distinct English wordings become senses ("ghost of; color of"), the longest
definition wins (others kept in `other_definitions`), the grammar tag follows
the majority, and the absorbed ids are recorded in the survivor's `merged_from`
and `history`. Where copies disagree on grammar with no majority, a row goes to
the review queue. Review rows and other references to absorbed ids are
re-pointed at the survivor.
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

from src.core.dictionary_merge import merge_group  # noqa: E402
from src.database.dictionary_db import DictionaryDB  # noqa: E402

REPORT = Path(__file__).resolve().parents[1] / "data" / "dedupe" / "report.json"


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the merges and delete absorbed copies")
    args = ap.parse_args()

    db = DictionaryDB()
    col = db.dictionary_collection
    reviews = db.db["translation_reviews"]

    groups: dict[str, list[dict]] = defaultdict(list)
    for doc in col.find({}):
        head = (doc.get("chuukese_word") or "").strip().lower()
        if head:
            groups[head].append(doc)
    dups = {h: g for h, g in groups.items() if len(g) > 1}

    plan = []
    tally: Counter = Counter()
    for head, entries in sorted(dups.items()):
        result = merge_group(entries)
        tally["groups"] += 1
        tally["absorbed"] += len(result["absorbed"])
        tally["identical" if result["identical"] else "merged"] += 1
        if result["grammar_conflict"]:
            tally["grammar_conflicts"] += 1
            if result["grammar_conflict"]["majority"] is None:
                tally["grammar_ties_for_review"] += 1
        plan.append(
            {
                "headword": head,
                "survivor": str(result["survivor"]["_id"]),
                "absorbed": [str(i) for i in result["absorbed"]],
                "identical": result["identical"],
                "update": {k: v for k, v in result["update"].items()},
                "grammar_conflict": result["grammar_conflict"],
                "copies": [
                    {"id": str(e["_id"]), "english": e.get("english_translation"), "grammar": e.get("grammar"), "definition": e.get("definition")}
                    for e in entries
                ],
            }
        )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(), "tally": dict(tally), "plan": plan}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"entries {col.estimated_document_count()}, duplicate groups {tally['groups']}, copies to remove {tally['absorbed']}")
    print(f"  identical groups {tally['identical']}, groups needing a merge {tally['merged']}")
    print(f"  grammar conflicts {tally['grammar_conflicts']} (ties sent to review: {tally['grammar_ties_for_review']})")
    print(f"report: {REPORT}")
    if not args.apply:
        print("\nReport only. Re-run with --apply to merge.")
        return 0

    now = datetime.now(timezone.utc)
    done = 0
    for item in plan:
        survivor_id = next(e["_id"] for e in dups[item["headword"]] if str(e["_id"]) == item["survivor"])
        absorbed_ids = [e["_id"] for e in dups[item["headword"]] if str(e["_id"]) in set(item["absorbed"])]
        survivor = next(e for e in dups[item["headword"]] if e["_id"] == survivor_id)
        update = dict(item["update"])
        before = {k: survivor.get(k) for k in update}
        update.update({"merged_from": [str(i) for i in absorbed_ids], "date_modified": now})
        history = {
            "at": now,
            "by": "dedupe_dictionary.py",
            "kind": "merge",
            "merged_from": [str(i) for i in absorbed_ids],
            "before": before,
            "after": item["update"],
            "absorbed_copies": [c for c in item["copies"] if c["id"] != item["survivor"]],
        }
        retry(lambda: col.update_one({"_id": survivor_id}, {"$set": update, "$push": {"history": history}}))
        retry(lambda: col.delete_many({"_id": {"$in": absorbed_ids}}))

        # Re-point review rows at the survivor; drop a duplicate of a kind it already has.
        for kind in ("translation", "grammar"):
            has = reviews.find_one({"entry_id": item["survivor"], "kind": kind}, {"_id": 1})
            if has:
                retry(lambda: reviews.delete_many({"entry_id": {"$in": item["absorbed"]}, "kind": kind}))
            else:
                retry(lambda: reviews.update_many({"entry_id": {"$in": item["absorbed"]}, "kind": kind}, {"$set": {"entry_id": item["survivor"]}}))

        conflict = item["grammar_conflict"]
        if conflict and conflict["majority"] is None:
            retry(
                lambda: reviews.update_one(
                    {"entry_id": item["survivor"], "kind": "grammar"},
                    {
                        "$set": {
                            "entry_id": item["survivor"],
                            "headword": survivor.get("chuukese_word"),
                            "kind": "grammar",
                            "outcome": "merge_conflict",
                            "tier": "review",
                            "status": "pending",
                            "current": {"grammar": survivor.get("grammar"), "grammar_modifier": survivor.get("grammar_modifier"), "definition": survivor.get("definition")},
                            "proposed": {"grammar": survivor.get("grammar")},
                            "evidence": {"notes": [f"Merged copies were tagged {', '.join(f'{g} ×{n}' for g, n in conflict['votes'].items())}; no majority. Confirm the tag."]},
                            "updated_at": now,
                        },
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
            )
        done += 1
        time.sleep(0.05)
        if done % 100 == 0:
            print(f"  {done}/{len(plan)} merged")
    print(f"\nmerged {done} groups; entries now {col.estimated_document_count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
