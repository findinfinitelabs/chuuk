#!/usr/bin/env python3
"""
Give every authored line of the Conversation Builder flow a Chuukese version.

Lines in src/data/conversation_flow.json that have no `chk` are translated
English → Chuukese with the Helsinki model and stored in the
``conversation_phrases`` collection flagged ``mt: true``. A line someone has
already corrected on the page (``mt: false``) is never overwritten; pass
--force to redo machine translations.

    .venv/bin/python scripts/fill_conversation_phrases.py
    .venv/bin/python scripts/fill_conversation_phrases.py --dry-run

Slots such as {{scripture}} are kept out of the translator: the text is
translated in pieces around them and the slot is put back.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# The engine comes from .env (MADLAD locally, when available).

FLOW = PROJECT_ROOT / "src" / "data" / "conversation_flow.json"
_SLOT = re.compile(r"(\{\{\w+\}\})")


def log(msg: str) -> None:
    print(msg, flush=True)


def collect(flow: dict) -> list[tuple[str, str]]:
    """(phrase_id, english) for everything that may need Chuukese."""
    rows: list[tuple[str, str]] = []
    for sid, openers in flow["subject_openers"].items():
        for o in openers:
            if not o.get("chk"):
                rows.append((o["id"], o["en"]))
    for nid, node in flow["nodes"].items():
        rows.append((f"node:{nid}:title", node["title"]["en"]))
        for key in ("say", "think"):
            for p in node.get(key, []):
                if p.get("en") and not p.get("chk") and not p.get("from"):
                    rows.append((p["id"], p["en"]))
        for r in node.get("responses", []):
            rows.append((f"node:{nid}:resp:{r['kind']}:label", r["label"]["en"]))
            for t in r.get("they", []):
                if t.get("en") and not t.get("chk"):
                    rows.append((t["id"], t["en"]))
    seen, out = set(), []
    for pid, en in rows:
        if pid not in seen:
            seen.add(pid)
            out.append((pid, en))
    return out


def translate_with_slots(translator, text: str) -> str:
    parts = _SLOT.split(text)
    out = []
    for part in parts:
        if _SLOT.fullmatch(part) or not part.strip():
            out.append(part)
        else:
            lead = part[: len(part) - len(part.lstrip())]
            trail = part[len(part.rstrip()):]
            chk = (translator.translate_english_to_chuukese(part.strip()) or "").strip()
            if out and _SLOT.fullmatch(out[-1]) and not lead and chk[:1].isalnum():
                lead = " "
            out.append(lead + chk + trail)
    return "".join(out).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Machine-translate the authored Conversation Builder lines")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Redo lines that are already machine translated")
    args = parser.parse_args()

    with open(FLOW, encoding="utf-8") as f:
        flow = json.load(f)
    rows = collect(flow)
    log(f"{len(rows)} lines in the flow")

    from src.database.dictionary_db import DictionaryDB

    db = DictionaryDB()
    col = db.db["conversation_phrases"] if db.db is not None else None
    existing = {d["phrase_id"]: d for d in col.find({}, {"_id": 0})} if col is not None else {}
    todo = []
    for pid, en in rows:
        cur = existing.get(pid)
        if cur and not cur.get("mt"):
            continue  # corrected by a person: keep
        if cur and cur.get("mt") and cur.get("en") == en and not args.force:
            continue
        todo.append((pid, en))
    log(f"{len(todo)} to translate")
    if not todo:
        return 0

    from src.training.trainer_factory import engine_display_name, get_translator

    translator = get_translator()
    if not translator.setup_models():
        log("❌ translator not available")
        return 1
    engine = engine_display_name()
    now = datetime.now(timezone.utc)
    for i, (pid, en) in enumerate(todo, 1):
        chk = translate_with_slots(translator, en)
        log(f"   [{i}/{len(todo)}] {pid}: {en} → {chk}")
        if args.dry_run or col is None:
            continue
        col.update_one(
            {"phrase_id": pid},
            {"$set": {"phrase_id": pid, "en": en, "chk": chk, "mt": True, "engine": engine, "filled_at": now}},
            upsert=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
