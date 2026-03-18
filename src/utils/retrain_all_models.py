#!/usr/bin/env python3
"""
Complete Model Retraining Pipeline
Retrains both Helsinki-NLP and Ollama models using current database data
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.database.dictionary_db import DictionaryDB
from src.training.helsinki_trainer import HelsinkiFineTuner
from src.translation.llm_trainer import ChuukeseLLMTrainer


def main():
    """Main retraining pipeline"""
    print("=" * 80)
    print("🚀 COMPLETE MODEL RETRAINING PIPELINE")
    print("=" * 80)
    print()

    # Step 1: Check database
    print("📊 Step 1: Checking database...")
    db = DictionaryDB()
    stats = db.get_statistics()

    total_entries = stats.get("total_entries", 0)
    total_words = stats.get("total_words", 0)
    total_phrases = stats.get("total_phrases", 0)

    print(f"   ✓ Total dictionary entries: {total_entries}")
    print(f"   ✓ Words: {total_words}")
    print(f"   ✓ Phrases: {total_phrases}")
    print()

    if total_entries == 0:
        print("❌ ERROR: No data in database. Please upload dictionary data first.")
        return False

    # Step 2: Train Helsinki-NLP models
    print("=" * 80)
    print("🔧 Step 2: Training Helsinki-NLP Models")
    print("=" * 80)
    print()

    helsinki_trainer = HelsinkiFineTuner()

    print("📚 Training Chuukese → English model...")
    success_chk_to_en = helsinki_trainer.fine_tune_model(
        direction="chk_to_en", num_epochs=3, batch_size=2, learning_rate=3e-5
    )

    if success_chk_to_en:
        print("✅ Chuukese → English model trained successfully!")
    else:
        print("⚠️ Warning: Chuukese → English training had issues")
    print()

    print("📚 Training English → Chuukese model...")
    success_en_to_chk = helsinki_trainer.fine_tune_model(
        direction="en_to_chk", num_epochs=3, batch_size=2, learning_rate=3e-5
    )

    if success_en_to_chk:
        print("✅ English → Chuukese model trained successfully!")
    else:
        print("⚠️ Warning: English → Chuukese training had issues")
    print()

    # Step 3: Train Ollama model
    print("=" * 80)
    print("🤖 Step 3: Training Ollama Model")
    print("=" * 80)
    print()

    ollama_trainer = ChuukeseLLMTrainer()

    # Check if Ollama is installed
    if not ollama_trainer.check_ollama_installation():
        print("⚠️ Ollama is not running. Skipping Ollama training.")
        print("   To train Ollama model:")
        print("   1. Install Ollama from https://ollama.com")
        print("   2. Run: ollama pull llama3.2:3b")
        print("   3. Re-run this script")
        ollama_success = False
    else:
        # Train Ollama
        ollama_success = ollama_trainer.train_full_pipeline()

        if ollama_success:
            print("✅ Ollama model trained successfully!")
            print()
            print("🧪 Testing Ollama model...")
            ollama_trainer.test_model()
        else:
            print("⚠️ Warning: Ollama training had issues")
    print()

    # Summary
    print("=" * 80)
    print("📋 TRAINING SUMMARY")
    print("=" * 80)
    print(f"   Helsinki Chuukese → English: {'✅ SUCCESS' if success_chk_to_en else '❌ FAILED'}")
    print(f"   Helsinki English → Chuukese: {'✅ SUCCESS' if success_en_to_chk else '❌ FAILED'}")
    print(f"   Ollama Model:                {'✅ SUCCESS' if ollama_success else '⚠️ SKIPPED/FAILED'}")
    print()

    if success_chk_to_en and success_en_to_chk:
        print("🎉 Helsinki-NLP models trained successfully!")
        print("   Models saved in:")
        print("   - models/helsinki-chuukese_chuukese_to_english/finetuned")
        print("   - models/helsinki-chuukese_english_to_chuukese/finetuned")
        print()

    if ollama_success:
        print("🎉 Ollama model trained successfully!")
        print("   Model name: chuukese-translator")
        print("   Test with: ollama run chuukese-translator")
        print()

    print("=" * 80)
    print("✨ RETRAINING COMPLETE!")
    print("=" * 80)

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Training interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
