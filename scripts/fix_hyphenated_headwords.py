#!/usr/bin/env python3
"""
Make hyphenated dictionary headwords whole words.

The source dictionary writes bound suffixes with a hyphen: "wis-ach" (our
duty), "ekiek-in" (his thinking). Nobody writes the hyphen in running text, so
sentence analysis reported "wisach" as missing while a "wis-ach" entry sat in
the database. This script:

  * "stem-suffix"          -> headword "stemsuffix"; keeps stem, suffix and the
                              suffix gloss as fields; keeps the hyphenated form
                              in `aliases`; adds the gloss to the definition
  * "base, -ei, -ók, ..."  -> headword "base"; the suffix list moves to
                              `suffix_forms`; original kept in `aliases`
  * joined twin exists     -> merge the hyphenated entry into the twin (fill
                              empty fields, union aliases/examples) and delete
                              the hyphenated document

Dry run by default. Pass --apply to write. Every Cosmos call is retried on
429 and paced so the run never trips the request-unit limit.

    .venv/bin/python scripts/fix_hyphenated_headwords.py            # report
    .venv/bin/python scripts/fix_hyphenated_headwords.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PACE_SECONDS = 0.25  # between Cosmos calls

# Bound suffix -> gloss. Only suffixes we are sure of; anything else is
# recorded without a gloss rather than guessed.
SUFFIX_GLOSS = {
    "i": "my / me", "ei": "me", "ii": "my",
    "om": "your (sg.)", "óm": "your (sg.)", "um": "your (sg.)", "úm": "your (sg.)",
    "ok": "you (sg.)", "ók": "you (sg.)", "uk": "you (sg.)", "úk": "you (sg.)",
    "n": "his / her / its", "an": "his / her / its", "in": "his / her / its", "un": "his / her / its", "ún": "his / her / its",
    "ach": "our (incl.)", "kich": "us (incl.)",
    "em": "our (excl.)", "kem": "us (excl.)",
    "emi": "your (pl.)", "kemi": "you (pl.)",
    "er": "their", "ar": "their", "iir": "their / them", "r": "them",
    "lo": "away (directional)", "ló": "away (directional)",
    "ta": "up (directional)", "tá": "up (directional)",
    "tiw": "down (directional)", "to": "toward the speaker (directional)",
}

SINGLE = re.compile(r"^([^\s,/-]+)-([^\s,/-]+)$")
MULTI = re.compile(r"^([^\s,/-]+)\s*,\s*(.+)$")


def retry(fn, attempts: int = 8):
    for i in range(attempts):
        try:
            result = fn()
            time.sleep(PACE_SECONDS)
            return result
        except Exception as exc:  # noqa: BLE001
            text = str(exc)
            if "16500" not in text and "429" not in text and "TooManyRequests" not in text:
                raise
            m = re.search(r"RetryAfterMs=(\d+)", text)
            wait = (int(m.group(1)) / 1000 if m else 1.0) + 1.5 * (i + 1)
            print(f"   ⏳ throttled, waiting {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError("Cosmos kept throttling after retries")


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or v == [] or v == {}


def plan_entry(doc: dict, field: str, twin: dict | None, twin_coll: str | None = None) -> dict | None:
    head = (doc.get(field) or "").strip()
    out = {"_id": doc["_id"], "old": head, "field": field}
    if any(ch.isdigit() for ch in head):
        out.update(kind="skip", reason="contains digits (scripture reference, not a word)")
        return out
    m = SINGLE.match(head)
    if m:
        stem, suffix = m.group(1), m.group(2)
        new = stem + suffix
        gloss = SUFFIX_GLOSS.get(suffix.lower())
        fields = {"stem": stem, "suffix": "-" + suffix}
        if gloss:
            fields["suffix_gloss"] = gloss
        out.update(kind="join", new=new, fields=fields)
    else:
        m = MULTI.match(head)
        if not m and re.fullmatch(r"[^\s,/-]+(-[^\s,/-]+){2,}", head):
            # Two bound suffixes: "uwei-uk-ló" -> "uweiukló", stem "uwei", suffix "-uk-ló".
            stem, rest = head.split("-", 1)
            out.update(kind="join", new=head.replace("-", ""), fields={"stem": stem, "suffix": "-" + rest})
            out["aliases"] = sorted({head} | set(doc.get("aliases") or []))
            if twin is None:
                return out
        if not m and out.get("kind") != "join":
            out.update(kind="skip", reason="pattern not recognised")
            return out
        if m:
            base, rest = m.group(1), m.group(2)
            forms = [f.strip() for f in re.split(r"[,/]", rest) if f.strip()]
            out.update(kind="base", new=base, fields={"suffix_forms": forms})
    out["aliases"] = sorted({head} | set(doc.get("aliases") or []))
    if twin is not None:
        out.update(kind="merge", twin_id=twin["_id"], twin_coll=twin_coll,
                   twin_head=twin.get("chuukese_word") or twin.get("chuukese_phrase"))
        fill = {}
        for key in ("english_translation", "definition", "grammar", "grammar_modifier", "notes", "citation", "scripture"):
            if blank(twin.get(key)) and not blank(doc.get(key)):
                fill[key] = doc[key]
        if not blank(twin.get("definition")) and not blank(doc.get("definition")) \
                and doc["definition"].strip().lower() != twin["definition"].strip().lower():
            fill["notes"] = ((twin.get("notes") or "").strip() + f"\nAlso: {doc['definition'].strip()}").strip()
        examples = list(twin.get("examples") or [])
        for ex in doc.get("examples") or []:
            if ex not in examples:
                examples.append(ex)
        if examples != list(twin.get("examples") or []):
            fill["examples"] = examples
        out["fill"] = fill
        out["aliases"] = sorted(set(out["aliases"]) | set(twin.get("aliases") or []))
    else:
        definition = (doc.get("definition") or doc.get("english_translation") or "").strip()
        gloss = out["fields"].get("suffix_gloss")
        if gloss and f"-{out['fields']['suffix'].lstrip('-')} =" not in definition:
            out["new_definition"] = (definition + f" [{out['fields']['suffix']} = {gloss}]").strip()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run)")
    args = parser.parse_args()

    from src.database.dictionary_db import DictionaryDB
    db = DictionaryDB()
    col = db.dictionary_collection
    if col is None:
        print("❌ no database connection")
        return 1

    sources = [
        ("dictionary_entries", db.dictionary_collection, "chuukese_word"),
        ("phrases", db.phrases_collection, "chuukese_phrase"),
    ]
    plans = []
    for coll_name, coll, field in sources:
        print(f"Loading hyphenated headwords from {coll_name} (one query)…")
        docs = retry(lambda: list(coll.find({field: {"$regex": "^[^\\s]*-[^\\s]*$|^[^\\s,/]+\\s*,\\s*-"}})))
        docs = [d for d in docs if not any(ch.isdigit() for ch in (d.get(field) or ""))]
        print(f"   {len(docs)} entries")

        candidates = set()
        for d in docs:
            head = (d.get(field) or "").strip()
            m = SINGLE.match(head) or MULTI.match(head)
            if m:
                candidates.add(m.group(1) + (m.group(2) if SINGLE.match(head) else ""))
        variants = sorted(candidates | {c.capitalize() for c in candidates})
        # Whole-word twins may sit in either collection; the dictionary wins.
        twins: dict[str, tuple[str, dict]] = {}
        for tname, tcoll, tfield in sources:
            for i in range(0, len(variants), 300):
                chunk = variants[i : i + 300]
                for t in retry(lambda c=tcoll, f=tfield, ch=chunk: list(c.find({f: {"$in": ch}}))):
                    key = (t.get(tfield) or "").strip().lower()
                    if key not in twins or (tname == "dictionary_entries" and twins[key][0] != "dictionary_entries"):
                        twins[key] = (tname, t)
        print(f"   {len(twins)} already exist as whole words")

        for d in docs:
            p = plan_entry(d, field, None)
            if p and p.get("new"):
                hit = twins.get(p["new"].lower())
                if hit is not None and hit[1]["_id"] != d["_id"]:
                    p = plan_entry(d, field, hit[1], hit[0])
            p["collection"] = coll_name
            plans.append(p)

    colls = {name: coll for name, coll, _ in sources}
    kinds = {}
    for p in plans:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print("\nPlan:", ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    print(f"{'old':<40} {'action':<6} {'new':<28} notes")
    shown = 0
    for p in plans:
        shown += 1
        if shown > 60 and p["kind"] == "merge" and not p.get("fill"):
            continue
        note = ""
        if p["kind"] == "merge":
            note = f"into {p['twin_coll']} '{p['twin_head']}'" + (f", fills {sorted(p['fill'])}" if p["fill"] else "")
        elif p["kind"] == "join":
            note = p["fields"].get("suffix_gloss") or "(suffix gloss unknown)"
        elif p["kind"] == "base":
            note = "forms: " + ", ".join(p["fields"]["suffix_forms"])
        elif p["kind"] == "skip":
            note = p["reason"]
        print(f"{p['old']:<40} {p['kind']:<6} {p.get('new', ''):<28} {note}")

    report = PROJECT_ROOT / "logs" / f"hyphen_headwords_{datetime.now():%Y%m%d_%H%M}.json"
    report.parent.mkdir(exist_ok=True)
    with open(report, "w", encoding="utf-8") as f:
        json.dump([{k: (str(v) if k in ("_id", "twin_id") else v) for k, v in p.items()} for p in plans], f, ensure_ascii=False, indent=1, default=str)
    print(f"\nReport: {report}")

    if not args.apply:
        print("Dry run. Re-run with --apply to write.")
        return 0

    stamp = datetime.now(timezone.utc).isoformat()
    done = {"join": 0, "base": 0, "merge": 0, "skip": 0}
    for p in plans:
        col = colls[p["collection"]]
        if p["kind"] == "skip":
            done["skip"] += 1
            continue
        if p["kind"] == "merge":
            tcol = colls[p["twin_coll"]]
            update = dict(p["fill"])
            update.update(p.get("fields") or {})
            update["aliases"] = p["aliases"]
            update["last_modified"] = stamp
            retry(lambda: tcol.update_one({"_id": p["twin_id"]}, {"$set": update}))
            retry(lambda: col.delete_one({"_id": p["_id"]}))
        else:
            update = dict(p["fields"])
            update[p["field"]] = p["new"]
            update["aliases"] = p["aliases"]
            update["last_modified"] = stamp
            if p.get("new_definition"):
                update["definition"] = p["new_definition"]
            retry(lambda: col.update_one({"_id": p["_id"]}, {"$set": update}))
        done[p["kind"]] += 1
        if done["join"] + done["base"] + done["merge"] <= 20 or (done["join"] + done["base"] + done["merge"]) % 100 == 0:
            print(f"   ✓ {p['old']} → {p['new']} ({p['kind']})")
    print("\nApplied:", done)
    print("Restart the app (or wait for the cache TTL) so the analysis index picks up the new headwords.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
