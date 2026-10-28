#!/usr/bin/env python3
"""
Distil MADLAD into Helsinki: translate real Chuukese sentences with the
fine-tuned MADLAD-400 model on this machine and write the pairs out as
synthetic training data for the small Helsinki OPUS-MT model that serves
in Azure.

MADLAD (3B, needs a GPU or 12 GB of RAM) knows Chuukese; Helsinki (77M, runs
on 2 vCPU) does not. The adapter weights cannot be shared between the two
architectures, but MADLAD's output can teach Helsinki: this is standard
teacher-student distillation.

Sources of Chuukese sentences (all read-only):
  - Cosmos: translation-game articles, article-analysis paragraphs,
    saved Watchtower Library searches
  - a text file of one sentence per line (--input)

Sentences that already have a confirmed human pair are skipped. Output is a
JSON list of {chuukese, english, source, model, score} that
scripts/retrain_with_latest_data.py consumes through --distilled.

Run from the project root, with TRANSLATION_ENGINE=madlad and the trained
adapter in models/madlad400-chuukese/:

    .venv/bin/python scripts/distill_madlad.py --limit 5000
    .venv/bin/python scripts/distill_madlad.py --input my_sentences.txt --roundtrip
    .venv/bin/python scripts/retrain_with_latest_data.py --distilled training_data/distilled_madlad_20261028.json

Then evaluate before trusting it: compare the Helsinki eval report before and
after, and drop the distilled file if BLEU or chrF fell.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MIN_WORDS = 4
MAX_WORDS = 60
# A faithful English translation of Chuukese runs close to the same length;
# anything far outside this band is a hallucination or a truncation.
MIN_RATIO = 0.45
MAX_RATIO = 2.5
BAD_OUTPUT = ("Translation error", "Translation model not available")

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def log(msg: str) -> None:
    print(msg, flush=True)


def norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def words(text: str) -> list[str]:
    return _WORD.findall(text or "")


# ---------------------------------------------------------------------------
# Sentence sources
# ---------------------------------------------------------------------------


def _sentence_text(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("text_only") or item.get("text") or item.get("chuukese") or ""
    return ""


def from_db() -> tuple[list[dict], set[str]]:
    """Chuukese sentences from Cosmos, and the normalised Chuukese of every
    pair we already hold (so distillation never overrides a human pair)."""
    from src.database.dictionary_db import DictionaryDB
    from src.training.continuous_trainer import TrainingPairCollector

    db = DictionaryDB()
    if not db.client:
        log("⚠️  No database connection; only --input sentences will be used.")
        return [], set()

    known = set()
    for p in TrainingPairCollector().collect_all(min_confidence=0):
        known.add(norm(p["chuukese"]))
    log(f"   {len(known):,} Chuukese texts already paired in the database")

    found: list[dict] = []

    def add(text: str, source: str):
        text = re.sub(r"\s+", " ", (text or "")).strip()
        if text:
            found.append({"chuukese": text, "source": source})

    try:
        for doc in db.db["game_articles"].find({}, {"chuukese_sentences": 1}):
            for item in doc.get("chuukese_sentences") or []:
                add(_sentence_text(item), "game_articles")
    except Exception as e:
        log(f"⚠️  game_articles: {e}")
    try:
        for doc in db.db["article_analysis_paragraphs"].find({}, {"paragraph.sentences": 1}):
            for s in (doc.get("paragraph") or {}).get("sentences") or []:
                # Sentences with an English parallel are already real pairs.
                if not (s.get("english_text") or "").strip():
                    add(s.get("text_only") or s.get("chuukese"), "article_analysis")
    except Exception as e:
        log(f"⚠️  article_analysis_paragraphs: {e}")
    try:
        for doc in db.db["wol_searches"].find({}, {"results.text": 1}):
            for r in doc.get("results") or []:
                add(r.get("text"), "wol_searches")
    except Exception as e:
        log(f"⚠️  wol_searches: {e}")

    log(f"   {len(found):,} sentences read from the database")
    return found, known


def from_file(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append({"chuukese": line, "source": path.name})
    log(f"   {len(rows):,} sentences read from {path}")
    return rows


def select_sentences(rows: list[dict], known: set[str], done: set[str], limit: int | None) -> list[dict]:
    """Unique, sentence-length, not already paired, not already distilled."""
    seen = set()
    out = []
    for r in rows:
        text = r["chuukese"]
        n = norm(text)
        if n in seen or n in known or n in done:
            continue
        count = len(words(text))
        if count < MIN_WORDS or count > MAX_WORDS:
            continue
        # Mostly-ASCII lines are English or citations, not Chuukese prose.
        letters = [c for c in text if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.5:
            continue
        seen.add(n)
        out.append(r)
        if limit and len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# Quality filters
# ---------------------------------------------------------------------------


def accept(chuukese: str, english: str) -> tuple[bool, str]:
    """Whether a MADLAD output is worth teaching to Helsinki."""
    if not english or any(b in english for b in BAD_OUTPUT):
        return False, "model_error"
    if norm(english) == norm(chuukese):
        return False, "echo"
    n_chk, n_en = len(words(chuukese)), len(words(english))
    if n_en < 2:
        return False, "too_short"
    ratio = n_en / max(n_chk, 1)
    if ratio < MIN_RATIO or ratio > MAX_RATIO:
        return False, "length_ratio"
    # English should be mostly plain letters; a run of accented words means
    # the model copied Chuukese through.
    en_words = words(english)
    accented = sum(1 for w in en_words if any(ord(c) > 127 for c in w))
    if accented / max(len(en_words), 1) > 0.3:
        return False, "not_english"
    # Degenerate repetition ("the the the ...").
    if len(set(w.lower() for w in en_words)) < max(2, len(en_words) // 3):
        return False, "repetitive"
    return True, "ok"


def overlap(a: str, b: str) -> float:
    """Share of a's words found in b, accent-insensitive. Used for the
    optional round-trip check."""
    aw = {norm(w) for w in words(a)}
    bw = {norm(w) for w in words(b)}
    return len(aw & bw) / max(len(aw), 1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Distil MADLAD translations into synthetic Helsinki training pairs")
    parser.add_argument("--input", action="append", default=[], metavar="FILE", help="Text file, one Chuukese sentence per line (repeatable)")
    parser.add_argument("--no-db", action="store_true", help="Do not read sentences from Cosmos")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of new sentences to translate")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--output", default=None, help="Output JSON (default: training_data/distilled_madlad_<date>.json)")
    parser.add_argument("--resume", action="store_true", help="Append to --output, skipping sentences it already holds")
    parser.add_argument("--roundtrip", action="store_true", help="Also translate the English back to Chuukese and keep only pairs with --roundtrip-min word overlap")
    parser.add_argument("--roundtrip-min", type=float, default=0.5)
    args = parser.parse_args()

    out_path = Path(args.output) if args.output else PROJECT_ROOT / "training_data" / f"distilled_madlad_{datetime.now():%Y%m%d}.json"
    existing: list[dict] = []
    if args.resume and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)
        log(f"Resuming: {len(existing):,} pairs already in {out_path}")
    done = {norm(p["chuukese"]) for p in existing}

    log("Collecting sentences…")
    rows: list[dict] = []
    known: set[str] = set()
    if not args.no_db:
        rows, known = from_db()
    for raw in args.input:
        rows += from_file(Path(raw))
    todo = select_sentences(rows, known, done, args.limit)
    log(f"   {len(todo):,} sentences to translate")
    if not todo:
        return 0

    from src.translation.madlad_translator import MadladChuukeseTranslator

    log("Loading MADLAD…")
    translator = MadladChuukeseTranslator()
    if not translator.available:
        log("❌ MADLAD is not available (base model download or adapter failed). See logs above.")
        return 1
    log(f"   loaded from: {translator.loaded_from}")

    stats: dict[str, int] = {}
    kept: list[dict] = []
    chunk = max(1, args.batch_size)
    for start in range(0, len(todo), chunk):
        batch = todo[start : start + chunk]
        texts = [r["chuukese"] for r in batch]
        try:
            english = translator.translate_batch(texts, "chk_to_en", batch_size=chunk)
        except Exception as e:
            log(f"⚠️  batch {start // chunk} failed: {e}")
            stats["batch_error"] = stats.get("batch_error", 0) + len(batch)
            continue
        back = None
        if args.roundtrip:
            try:
                back = translator.translate_batch(english, "en_to_chk", batch_size=chunk)
            except Exception as e:
                log(f"⚠️  round trip failed for batch {start // chunk}: {e}")
        for i, (row, en) in enumerate(zip(batch, english)):
            en = (en or "").strip()
            ok, reason = accept(row["chuukese"], en)
            score = None
            if ok and back is not None:
                score = round(overlap(row["chuukese"], back[i]), 3)
                if score < args.roundtrip_min:
                    ok, reason = False, "roundtrip"
            stats[reason] = stats.get(reason, 0) + 1
            if ok:
                kept.append(
                    {
                        "chuukese": row["chuukese"],
                        "english": en,
                        "source": f"madlad_distill:{row['source']}",
                        "type": "sentence",
                        "model": translator.loaded_from,
                        "roundtrip": score,
                    }
                )
        done_n = min(start + chunk, len(todo))
        log(f"   {done_n:,}/{len(todo):,} translated, {len(kept):,} kept")
        # Checkpoint so an interrupted run keeps its work.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(existing + kept, f, ensure_ascii=False, indent=1)

    log("")
    log(f"Kept {len(kept):,} of {len(todo):,} → {out_path}")
    for reason, n in sorted(stats.items(), key=lambda kv: -kv[1]):
        log(f"   {reason:<14} {n:,}")
    log("")
    log("Next: .venv/bin/python scripts/retrain_with_latest_data.py --direction both "
        f"--distilled {out_path.relative_to(PROJECT_ROOT) if out_path.is_relative_to(PROJECT_ROOT) else out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
