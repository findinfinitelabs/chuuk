#!/usr/bin/env python3
"""
Automated Helsinki-NLP training from database.
Pulls all entries from Cosmos DB, trains both translation directions,
then uploads the fine-tuned models to Azure Blob Storage.

Usage:
    python scripts/train_from_db.py [--epochs 3] [--batch-size 2] [--no-upload]
"""

import os
import sys
import json
import argparse
import shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def gather_training_pairs() -> list[dict]:
    """Pull all usable translation pairs from the database."""
    from src.database.dictionary_db import DictionaryDB

    log("Connecting to database...")
    db = DictionaryDB()

    pairs = []

    # Dictionary words/phrases/sentences
    log("Loading dictionary entries...")
    entries = list(db.dictionary_collection.find(
        {"search_direction": {"$ne": "en_to_chk"}},
        {"chuukese_word": 1, "english_translation": 1, "type": 1, "grammar": 1}
    ))
    for e in entries:
        chk = (e.get("chuukese_word") or "").strip()
        eng = (e.get("english_translation") or "").strip()
        if chk and eng and len(chk) > 1 and len(eng) > 2:
            pairs.append({"chuukese": chk, "english": eng})

    log(f"  Dictionary: {len(pairs):,} pairs")

    # Phrases collection
    phrase_count_before = len(pairs)
    phrases = list(db.phrases_collection.find(
        {},
        {"chuukese_sentence": 1, "chuukese_phrase": 1, "chuukese": 1, "english_translation": 1}
    ))
    for p in phrases:
        chk = (p.get("chuukese_sentence") or p.get("chuukese_phrase") or p.get("chuukese") or "").strip()
        eng = (p.get("english_translation") or "").strip()
        if chk and eng and len(chk) > 2 and len(eng) > 3:
            pairs.append({"chuukese": chk, "english": eng})
    log(f"  Phrases: {len(pairs) - phrase_count_before:,} pairs")

    log(f"Total training pairs: {len(pairs):,}")
    return pairs


def upload_models_to_blob(model_dirs: list[str]):
    """Upload fine-tuned model directories to Azure Blob Storage."""
    storage_account = os.environ.get("AZURE_STORAGE_ACCOUNT", "chuukdictmodels")
    container = "helsinki-models"

    try:
        from azure.storage.blob import BlobServiceClient

        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        account_key = os.environ.get("AZURE_STORAGE_KEY")

        if conn_str:
            client = BlobServiceClient.from_connection_string(conn_str)
        elif account_key:
            client = BlobServiceClient(
                account_url=f"https://{storage_account}.blob.core.windows.net",
                credential=account_key,
            )
        else:
            log("⚠️  No Azure Storage credentials found — skipping upload.")
            log("   Set AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_KEY.")
            return False

        # Ensure container exists
        try:
            client.create_container(container)
        except Exception:
            pass  # Already exists

        uploaded = 0
        for model_dir in model_dirs:
            model_path = Path(model_dir)
            if not model_path.exists():
                log(f"  Skipping {model_dir} (not found)")
                continue

            log(f"  Uploading {model_dir} ...")
            for file_path in model_path.rglob("*"):
                if file_path.is_file():
                    blob_name = str(file_path.relative_to(Path(".")))
                    blob_client = client.get_blob_client(container=container, blob=blob_name)
                    with open(file_path, "rb") as f:
                        blob_client.upload_blob(f, overwrite=True)
                    uploaded += 1

        log(f"✅ Uploaded {uploaded} files to blob storage")
        return True

    except ImportError:
        log("⚠️  azure-storage-blob not installed — skipping upload.")
        return False
    except Exception as e:
        log(f"❌ Upload error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Train Helsinki models from database")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=2, help="Batch size (keep 2-4 on CPU)")
    parser.add_argument("--no-upload", action="store_true", help="Skip upload to Azure Blob")
    parser.add_argument("--direction", choices=["both", "chk_to_en", "en_to_chk"], default="both",
                        help="Which direction(s) to train")
    args = parser.parse_args()

    log("=" * 70)
    log("Helsinki-NLP Automated Training from Database")
    log(f"Epochs: {args.epochs}  Batch size: {args.batch_size}  Direction: {args.direction}")
    log("=" * 70)

    # Gather data
    pairs = gather_training_pairs()
    if len(pairs) < 10:
        log("❌ Too few training pairs (<10). Aborting.")
        sys.exit(1)

    # Save a snapshot for reference
    snapshot = Path("training_data/latest_snapshot.json")
    snapshot.parent.mkdir(exist_ok=True)
    with open(snapshot, "w", encoding="utf-8") as f:
        json.dump(pairs, f, ensure_ascii=False, indent=2)
    log(f"Saved data snapshot → {snapshot}")

    # Train
    from src.training.helsinki_trainer import HelsinkiFineTuner

    def progress_cb(stage, progress, **kwargs):
        epoch = kwargs.get("epoch")
        total = kwargs.get("total_epochs")
        loss = kwargs.get("epoch_loss")
        parts = [f"[{stage}]"]
        if epoch and total:
            parts.append(f"epoch {epoch}/{total}")
        if loss is not None:
            parts.append(f"loss={loss:.4f}")
        log("  " + "  ".join(parts))

    trainer = HelsinkiFineTuner(progress_callback=progress_cb)

    directions = (
        ["chk_to_en", "en_to_chk"] if args.direction == "both"
        else [args.direction]
    )

    results = {}
    for direction in directions:
        label = "Chuukese→English" if direction == "chk_to_en" else "English→Chuukese"
        log(f"\n{'='*40}")
        log(f"Training {label}")
        log(f"{'='*40}")
        success = trainer.fine_tune_model(
            direction=direction,
            training_pairs=pairs,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=3e-5,
        )
        results[direction] = success
        log(f"{'✅' if success else '❌'} {label} {'done' if success else 'FAILED'}")

    log("\n" + "=" * 70)
    log("TRAINING SUMMARY")
    for d, ok in results.items():
        log(f"  {d}: {'SUCCESS' if ok else 'FAILED'}")
    log("=" * 70)

    if not args.no_upload and any(results.values()):
        log("\nUploading models to Azure Blob Storage...")
        model_dirs = [
            "models/helsinki-chuukese_chuukese_to_english/finetuned",
            "models/helsinki-chuukese_english_to_chuukese/finetuned",
        ]
        upload_models_to_blob(model_dirs)
    elif args.no_upload:
        log("Skipping upload (--no-upload)")

    all_ok = all(results.values())
    log(f"\n{'✅ All training completed!' if all_ok else '⚠️  Some training failed — check logs above.'}")

    # Write a status file for the GH Actions workflow to read
    status = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "success": all_ok,
        "total_pairs": len(pairs),
    }
    Path("logs").mkdir(exist_ok=True)
    with open("logs/training_status.json", "w") as f:
        json.dump(status, f, indent=2)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
