#!/usr/bin/env python3
"""
Retrain Helsinki-NLP OPUS-MT models with the most up-to-date validated training data.

Uses: training_data/chuukese_to_english_validated_20260228.json
      training_data/english_to_chuukese_validated.json

Run from project root:
    .venv/bin/python scripts/retrain_with_latest_data.py [--direction chk_to_en|en_to_chk|both] [--epochs N] [--batch-size N]
"""

import sys
import json
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so src.* imports resolve
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.training.helsinki_trainer import HelsinkiFineTuner


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_chk_to_en_pairs(data_file: Path) -> list:
    """
    Load and convert chuukese_to_english_validated_20260228.json into
    the training-pair format expected by HelsinkiFineTuner.

    Entry types handled:
      - word    : expand comma-separated meanings, prefix [grammar] tag
      - phrase  : treat as a single pair (no meaning expansion)
      - sentence: full sentence pair — included as-is and repeated for emphasis
      - scripture: full verse pair  — included as-is and repeated for emphasis
      - question: treated like sentences

    Sentence/scripture pairs are repeated SENTENCE_WEIGHT times because they
    are rare but represent the highest-quality full-context signal.
    """
    SENTENCE_WEIGHT = 5  # repeat sentence/scripture pairs this many times

    print(f"📂 Loading Chuukese→English data from: {data_file}")
    with open(data_file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    word_pairs = []
    sentence_pairs = []
    skipped = 0

    for entry in raw:
        chuukese = (entry.get("chuukese_word") or "").strip()
        english  = (entry.get("english_translation") or "").strip()
        grammar  = (entry.get("grammar") or "").strip()
        etype    = (entry.get("type") or "word").strip().lower()

        if not chuukese or not english:
            skipped += 1
            continue

        if etype in ("sentence", "scripture", "paragraph", "question"):
            # Full sentence / verse pair — use verbatim
            sentence_pairs.append({"chuukese": chuukese, "english": english})

        elif etype == "phrase":
            # Multi-word phrase — use verbatim, no grammar tag
            sentence_pairs.append({"chuukese": chuukese, "english": english})

        else:
            # word (default) — expand comma-separated meanings, NO grammar tag
            # so the model learns plain 'aramas' -> 'people', not '[noun] aramas' -> 'people'
            meanings = [m.strip() for m in english.split(",") if m.strip()]
            for meaning in meanings:
                word_pairs.append({
                    "chuukese": chuukese,
                    "english": meaning,
                })

    # Weight sentence/scripture/phrase pairs by repeating them
    weighted_sentence_pairs = sentence_pairs * SENTENCE_WEIGHT

    all_pairs = word_pairs + weighted_sentence_pairs

    print(f"   Raw entries            : {len(raw):,}")
    print(f"   Skipped                : {skipped:,}  (missing chuukese or english)")
    print(f"   Word pairs             : {len(word_pairs):,}")
    print(f"   Sentence/scripture/phrase pairs : {len(sentence_pairs):,}  "
          f"→ {len(weighted_sentence_pairs):,} after {SENTENCE_WEIGHT}× weighting")
    print(f"   Total training pairs   : {len(all_pairs):,}")
    return all_pairs


def load_en_to_chk_pairs(data_file: Path) -> list:
    """
    Load english_to_chuukese_validated.json.

    The file produced by EnhancedHelsinkiTrainer already has
    {'english': ..., 'chuukese': ...} keys.  If it uses the raw DB format
    ('english_translation' / 'chuukese_word') we remap and handle all types:
      - sentence/scripture/phrase → repeated SENTENCE_WEIGHT times
      - word → comma-expanded meanings
    """
    SENTENCE_WEIGHT = 5

    print(f"📂 Loading English→Chuukese data from: {data_file}")
    with open(data_file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not raw:
        print("   ⚠️  Empty file – skipping")
        return []

    first = raw[0]
    # Pre-processed format — already has 'english'/'chuukese' keys
    if "english" in first and "chuukese" in first:
        pairs = [{"english": e.get("english", ""), "chuukese": e.get("chuukese", "")}
                 for e in raw if e.get("english") and e.get("chuukese")]
        print(f"   Final pairs : {len(pairs):,}")
        return pairs

    # Raw DB / training-file format
    word_pairs = []
    sentence_pairs = []
    for entry in raw:
        chuukese = (entry.get("chuukese_word") or "").strip()
        english  = (entry.get("english_translation") or "").strip()
        grammar  = (entry.get("grammar") or "").strip()
        etype    = (entry.get("type") or "word").strip().lower()

        if not chuukese or not english:
            continue

        if etype in ("sentence", "scripture", "paragraph", "question", "phrase"):
            sentence_pairs.append({"english": english, "chuukese": chuukese})
        else:
            meanings = [m.strip() for m in english.split(",") if m.strip()]
            for meaning in meanings:
                word_pairs.append({"english": meaning, "chuukese": chuukese})

    all_pairs = word_pairs + sentence_pairs * SENTENCE_WEIGHT
    print(f"   Word pairs             : {len(word_pairs):,}")
    print(f"   Sentence/phrase pairs  : {len(sentence_pairs):,} → {len(sentence_pairs)*SENTENCE_WEIGHT:,} after {SENTENCE_WEIGHT}× weighting")
    print(f"   Total training pairs   : {len(all_pairs):,}")
    return all_pairs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Retrain Helsinki-NLP models for Chuukese translation"
    )
    parser.add_argument(
        "--direction",
        choices=["chk_to_en", "en_to_chk", "both"],
        default="chk_to_en",
        help="Which model direction to train (default: chk_to_en)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="Number of training epochs (default: 10)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Per-device batch size (default: 8)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=3e-5,
        help="Learning rate (default: 3e-5)",
    )
    parser.add_argument(
        "--save-steps",
        type=int,
        default=500,
        help="Save a checkpoint every N steps (default: 500)",
    )
    parser.add_argument(
        "--chk-en-file",
        default="training_data/chuukese_to_english_validated_20260228.json",
        help="Path to Chuukese→English training data file",
    )
    parser.add_argument(
        "--en-chk-file",
        default="training_data/english_to_chuukese_validated.json",
        help="Path to English→Chuukese training data file",
    )

    args = parser.parse_args()

    chk_en_path = PROJECT_ROOT / args.chk_en_file
    en_chk_path = PROJECT_ROOT / args.en_chk_file

    print("=" * 70)
    print("🚀 HELSINKI-NLP RETRAINING — Chuukese Translation Models")
    print("=" * 70)
    print(f"   Direction    : {args.direction}")
    print(f"   Epochs       : {args.epochs}")
    print(f"   Batch size   : {args.batch_size}")
    print(f"   Learning rate: {args.learning_rate}")
    print(f"   Save steps   : {args.save_steps}")
    print()

    trainer = HelsinkiFineTuner()

    results = {}

    # ---- Chuukese → English ------------------------------------------------
    if args.direction in ("chk_to_en", "both"):
        if not chk_en_path.exists():
            print(f"❌ File not found: {chk_en_path}")
            sys.exit(1)

        pairs = load_chk_to_en_pairs(chk_en_path)
        print()

        success = trainer.fine_tune_model(
            direction="chk_to_en",
            training_pairs=pairs,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            save_steps=args.save_steps,
        )
        results["chk_to_en"] = success
        print(f"\n{'✅' if success else '❌'} Chuukese→English training {'complete' if success else 'FAILED'}")

    # ---- English → Chuukese ------------------------------------------------
    if args.direction in ("en_to_chk", "both"):
        if not en_chk_path.exists():
            print(f"❌ File not found: {en_chk_path}")
            sys.exit(1)

        pairs = load_en_to_chk_pairs(en_chk_path)
        print()

        success = trainer.fine_tune_model(
            direction="en_to_chk",
            training_pairs=pairs,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            save_steps=args.save_steps,
        )
        results["en_to_chk"] = success
        print(f"\n{'✅' if success else '❌'} English→Chuukese training {'complete' if success else 'FAILED'}")

    # ---- Summary -----------------------------------------------------------
    print()
    print("=" * 70)
    print("📊 TRAINING SUMMARY")
    print("=" * 70)
    for direction, ok in results.items():
        label = "Chuukese→English" if direction == "chk_to_en" else "English→Chuukese"
        print(f"   {label}: {'✅ SUCCESS' if ok else '❌ FAILED'}")

    all_ok = all(results.values())
    if all_ok:
        print("\n🎉 All models retrained successfully!")
        print("   Fine-tuned weights saved to models/*/finetuned/")
    else:
        print("\n❌ One or more trainings failed. Check output above.")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
