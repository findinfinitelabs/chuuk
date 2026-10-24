#!/usr/bin/env python3
"""
Train the MADLAD-400 Chuukese ↔ English LoRA adapter.

Pulls pairs from Cosmos (dictionary, phrases, paragraphs, article analyses) plus
the parallel Bible corpus, holds out a fixed evaluation sample, optionally scores
the *untrained* base model on it (zero-shot baseline), trains the adapter, then
scores again so the before/after BLEU and chrF are side by side.

Run from the project root (Apple Silicon uses the Metal GPU automatically):

    .venv/bin/python scripts/train_madlad.py --eval-baseline
    .venv/bin/python scripts/train_madlad.py --epochs 3 --batch-size 8
    .venv/bin/python scripts/train_madlad.py --snapshot training_data/latest_snapshot.json   # offline, no DB
    .venv/bin/python scripts/train_madlad.py --eval-only                                      # score current weights

Outputs:
    models/madlad400-chuukese/lora/                 adapter + tokenizer
    models/madlad400-chuukese/lora/training_metrics.json
    models/madlad400-chuukese/eval_report.json      baseline vs. fine-tuned scores
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.translation.madlad_translator import MadladChuukeseTranslator, TranslationPair, model_root  # noqa: E402


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_json_pairs(path: Path) -> list[dict]:
    if not path.exists():
        log(f"⚠️  Not found, skipping: {path}")
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out = []
    for e in raw:
        chk = (e.get("chuukese") or e.get("chuukese_word") or "").strip()
        eng = (e.get("english") or e.get("english_translation") or "").strip()
        if chk and eng:
            out.append({"chuukese": chk, "english": eng, "source": e.get("source", path.stem)})
    log(f"   {path.name}: {len(out):,} pairs")
    return out


def load_db_pairs(min_confidence: float) -> list[dict]:
    from src.training.continuous_trainer import TrainingPairCollector

    log("Collecting pairs from database…")
    pairs = TrainingPairCollector().collect_all(min_confidence=min_confidence)
    log(f"   database: {len(pairs):,} pairs")
    return pairs


def dedupe(pairs: list[dict]) -> list[dict]:
    seen, out = set(), []
    for p in pairs:
        key = (p["chuukese"].lower(), p["english"].lower())
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def is_sentence(p: dict) -> bool:
    return " " in p["chuukese"].strip() and " " in p["english"].strip()


def assemble(args) -> tuple[list[dict], list[dict]]:
    """Return (training_pairs_with_weighting, held_out_eval_pairs)."""
    pairs: list[dict] = []
    if args.snapshot:
        pairs += load_json_pairs(PROJECT_ROOT / args.snapshot)
    else:
        pairs += load_db_pairs(args.min_confidence)
    bible = load_json_pairs(PROJECT_ROOT / args.bible_file) if args.bible_file else []

    pairs = dedupe(pairs + bible)
    log(f"Unique pairs: {len(pairs):,}")

    # Same cleaning the collector applies, re-run here so the Bible file and
    # --snapshot inputs get it too (idempotent for already-clean rows).
    from src.training.pair_cleaning import clean_pairs
    stats: dict = {}
    pairs = dedupe(clean_pairs(pairs, stats))
    log(f"Cleaning: kept {stats['kept']:,}, dropped {stats['dropped']:,}, normalised {stats['normalised']:,} → {len(pairs):,} unique")

    # Held-out eval sample, fixed seed, biased toward sentences (words are too noisy for BLEU)
    rng = random.Random(args.seed)
    sentences = [p for p in pairs if is_sentence(p)]
    words = [p for p in pairs if not is_sentence(p)]
    rng.shuffle(sentences)
    rng.shuffle(words)
    n_sent = min(len(sentences), int(args.eval_size * 0.8))
    n_word = min(len(words), args.eval_size - n_sent)
    eval_pairs = sentences[:n_sent] + words[:n_word]
    eval_keys = {(p["chuukese"].lower(), p["english"].lower()) for p in eval_pairs}
    train_pairs = [p for p in pairs if (p["chuukese"].lower(), p["english"].lower()) not in eval_keys]

    # Weight full sentences so ~13k single-word entries don't dominate
    weighted = []
    for p in train_pairs:
        weighted.extend([p] * (args.sentence_weight if is_sentence(p) else 1))
    rng.shuffle(weighted)

    if args.max_pairs and len(weighted) > args.max_pairs:
        weighted = weighted[: args.max_pairs]

    log(f"Train pairs: {len(train_pairs):,} unique → {len(weighted):,} after sentence weighting ×{args.sentence_weight}")
    log(f"Eval pairs : {len(eval_pairs):,} ({n_sent} sentences, {n_word} words) — excluded from training")
    return weighted, eval_pairs


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------

def evaluate(label: str, eval_pairs: list[dict], show: int = 5, use_adapter: bool = True) -> dict:
    t = MadladChuukeseTranslator(use_adapter=use_adapter)
    if not t.setup_models():
        log("❌ Could not load model for evaluation")
        return {}
    tp = [TranslationPair(p["chuukese"], p["english"]) for p in eval_pairs]
    log(f"Scoring {label} ({t.loaded_from}) on {len(tp)} pairs…")
    res = t.evaluate_translation_quality(tp)
    if not res:
        log("❌ Evaluation returned no scores")
        return {}
    res["loaded_from"] = t.loaded_from
    log(f"📊 {label}: chk→en BLEU {res['chuukese_to_english_bleu']} chrF {res['chuukese_to_english_chrf']}"
        f" | en→chk BLEU {res['english_to_chuukese_bleu']} chrF {res['english_to_chuukese_chrf']}")
    # A few concrete examples make the numbers legible
    sample = [p for p in eval_pairs if is_sentence(p)][:show]
    for p in sample:
        log(f"   CHK: {p['chuukese']}")
        log(f"   REF: {p['english']}")
        log(f"   HYP: {t.translate_chuukese_to_english(p['chuukese'])}")
    del t
    return res


def run_dir() -> Path:
    d = Path(model_root()) / "run"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_report() -> dict:
    f = Path(model_root()) / "eval_report.json"
    return json.load(open(f)) if f.exists() else {}


def write_report(report: dict) -> Path:
    out = Path(model_root()) / "eval_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return out


def merge_report(**updates) -> Path:
    """Read-modify-write so every phase persists its result immediately."""
    rep = read_report()
    rep.update(updates)
    return write_report(rep)


# ---------------------------------------------------------------------------
# Phases — each runs in its own interpreter so a native (Metal) crash in one
# phase cannot take the others down, and the GPU context starts clean.
# ---------------------------------------------------------------------------

def phase_baseline(args):
    eval_pairs = json.load(open(run_dir() / "eval_pairs.json"))
    res = evaluate("baseline", eval_pairs, use_adapter=False)
    merge_report(baseline=res)
    return bool(res)


def phase_train(args):
    from src.training.madlad_trainer import MadladFineTuner

    train_pairs = json.load(open(run_dir() / "train_pairs.json"))

    def progress(stage, pct, **kw):
        extra = " ".join(f"{k}={v}" for k, v in kw.items() if v is not None)
        log(f"{'' if pct is None else f'[{int(pct):3d}%] '}{stage} {extra}")

    tuner = MadladFineTuner(progress_callback=progress)
    ok = tuner.fine_tune_model(
        direction=args.direction,
        training_pairs=train_pairs,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        train_ffn=args.train_ffn,
        save_steps=args.save_steps,
        resume_adapter=not args.fresh,
        merge=args.merge,
    )
    metrics_file = Path(tuner.lora_path) / "training_metrics.json"
    merge_report(training_ok=ok, training_metrics=json.load(open(metrics_file)) if metrics_file.exists() else None)
    return ok


def phase_eval(args):
    eval_pairs = json.load(open(run_dir() / "eval_pairs.json"))
    res = evaluate("fine-tuned", eval_pairs)
    merge_report(finetuned=res)
    return bool(res)


PHASES = {"baseline": phase_baseline, "train": phase_train, "eval": phase_eval}


def run_phase(name: str, argv: list[str]) -> bool:
    """Spawn `this script --phase name` with the same interpreter; report signal/exit on failure."""
    import subprocess

    cmd = [sys.executable, __file__, "--phase", name] + argv
    log(f"▶ phase {name}: {' '.join(cmd[2:])}")
    rc = subprocess.call(cmd, cwd=str(PROJECT_ROOT))
    if rc != 0:
        why = f"signal {-rc}" if rc < 0 else f"exit code {rc}"
        log(f"❌ phase {name} failed ({why})")
        merge_report(**{f"{name}_error": why})
        return False
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Train / evaluate the MADLAD-400 Chuukese LoRA adapter")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=2)
    ap.add_argument("--learning-rate", type=float, default=2e-4)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--train-ffn", action="store_true", help="also adapt T5 feed-forward layers")
    ap.add_argument("--direction", choices=["both", "chk_to_en", "en_to_chk"], default="both")
    ap.add_argument("--save-steps", type=int, default=500)
    ap.add_argument("--fresh", action="store_true", help="ignore an existing adapter and start a new one")
    ap.add_argument("--merge", action="store_true", help="also write a merged full checkpoint (~6 GB)")

    ap.add_argument("--snapshot", help="JSON pairs file to use instead of the database")
    ap.add_argument("--bible-file", default="training_data/bible_parallel.json")
    ap.add_argument("--min-confidence", type=float, default=50)
    ap.add_argument("--sentence-weight", type=int, default=3)
    ap.add_argument("--max-pairs", type=int, default=0, help="cap weighted training examples (0 = all)")
    ap.add_argument("--eval-size", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)

    ap.add_argument("--eval-baseline", action="store_true", help="score the base model before training")
    ap.add_argument("--eval-only", action="store_true", help="only score the current weights, no training")
    ap.add_argument("--phase", choices=sorted(PHASES), help=argparse.SUPPRESS)  # internal
    args = ap.parse_args()

    if args.phase:
        sys.exit(0 if PHASES[args.phase](args) else 1)

    log("=" * 70)
    log("🚀 MADLAD-400 LoRA — Chuukese ⇄ English")
    log("=" * 70)

    train_pairs, eval_pairs = assemble(args)
    json.dump(train_pairs, open(run_dir() / "train_pairs.json", "w"), ensure_ascii=False)
    json.dump(eval_pairs, open(run_dir() / "eval_pairs.json", "w"), ensure_ascii=False)
    write_report({"config": vars(args), "pairs": len(train_pairs), "eval_pairs": len(eval_pairs),
                  "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")})

    argv = sys.argv[1:]
    if args.eval_only:
        ok = run_phase("eval", argv)
    else:
        ok = True
        if args.eval_baseline:
            ok = run_phase("baseline", argv)
        ok = ok and run_phase("train", argv)
        ok = ok and run_phase("eval", argv)

    report = read_report()
    log("=" * 70)
    log("📊 RESULTS (BLEU / chrF)")
    for key in ("baseline", "finetuned"):
        r = report.get(key)
        if r:
            log(f"   {key:10s} chk→en {r['chuukese_to_english_bleu']:5.1f} / {r['chuukese_to_english_chrf']:5.1f}"
                f"   en→chk {r['english_to_chuukese_bleu']:5.1f} / {r['english_to_chuukese_chrf']:5.1f}")
    log(f"📄 Report: {Path(model_root()) / 'eval_report.json'}")
    if ok:
        log("Restart the app (TRANSLATION_ENGINE=madlad) to serve the new adapter.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
