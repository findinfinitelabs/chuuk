#!/usr/bin/env python3
"""
Repeatable Helsinki-NLP Model Retraining System
Handles validated word entries with grammar context
Supports incremental updates as new data is added
"""

import os
import sys
import torch
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_trainer import EnhancedHelsinkiTrainer
from src.training.helsinki_trainer import HelsinkiFineTuner

class RepeatableModelRetrainer:
    """Handles repeatable retraining of Helsinki models with data integrity checks"""

    def __init__(self, models_dir: str = "models", training_dir: str = "training_data"):
        self.models_dir = Path(models_dir)
        self.training_dir = Path(training_dir)
        self.enhanced_trainer = EnhancedHelsinkiTrainer()

        # Create directories
        self.models_dir.mkdir(exist_ok=True)
        self.training_dir.mkdir(exist_ok=True)

        # Setup logging
        self.log_file = Path("logs/retraining.log")
        self.log_file.parent.mkdir(exist_ok=True)

    def log(self, message: str):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')

    def get_data_hash(self) -> str:
        """Get hash of current training data for change detection"""
        chk_pairs, en_pairs = self.enhanced_trainer.prepare_enhanced_training_data()

        # Create a deterministic representation
        data_repr = json.dumps({
            'chk_to_en': sorted([f"{p['chuukese']}->{p['english']}" for p in chk_pairs]),
            'en_to_chk': sorted([f"{p['english']}->{p['chuukese']}" for p in en_pairs])
        }, sort_keys=True)

        return hashlib.md5(data_repr.encode('utf-8')).hexdigest()

    def needs_retraining(self) -> bool:
        """Check if retraining is needed based on data changes"""
        current_hash = self.get_data_hash()
        hash_file = self.training_dir / "data_hash.txt"

        if not hash_file.exists():
            self.log("No previous data hash found - retraining needed")
            return True

        with open(hash_file, 'r') as f:
            previous_hash = f.read().strip()

        if current_hash != previous_hash:
            self.log(f"Data changed (hash: {current_hash[:8]} != {previous_hash[:8]}) - retraining needed")
            return True

        self.log("Data unchanged - retraining not needed")
        return False

    def prepare_training_data(self) -> bool:
        """Prepare and validate training data"""
        try:
            self.log("=== PREPARING TRAINING DATA ===")

            # Generate enhanced training data
            chk_pairs, en_pairs = self.enhanced_trainer.prepare_enhanced_training_data()

            # Analyze data quality
            stats = self.enhanced_trainer.analyze_data_quality()

            self.log(f"Training pairs: {stats['total_chk_to_en_pairs']:,} per direction")
            self.log(f"Unique Chuukese words: {stats['unique_chuukese_words']:,}")
            self.log(f"Unique English words: {stats['unique_english_words']:,}")

            # Save training data
            self.enhanced_trainer.save_training_data(str(self.training_dir))

            # Save data hash for change detection
            current_hash = self.get_data_hash()
            with open(self.training_dir / "data_hash.txt", 'w') as f:
                f.write(current_hash)

            self.log(f"Data hash: {current_hash[:8]}")
            self.log("✅ Training data prepared successfully")
            return True

        except Exception as e:
            self.log(f"❌ Failed to prepare training data: {e}")
            return False

    def retrain_model(self, direction: str) -> bool:
        """Retrain a specific model direction"""
        try:
            self.log(f"=== RETRAINING {direction.upper()} MODEL ===")

            # Load training data
            if direction == "chk_to_en":
                data_file = self.training_dir / "chuukese_to_english_validated.json"
            else:
                data_file = self.training_dir / "english_to_chuukese_validated.json"

            if not data_file.exists():
                self.log(f"❌ Training data file not found: {data_file}")
                return False

            with open(data_file, 'r', encoding='utf-8') as f:
                training_pairs = json.load(f)

            self.log(f"Loaded {len(training_pairs)} training pairs")

            # Initialize trainer
            trainer = HelsinkiFineTuner()

            # Convert to expected format
            formatted_pairs = []
            for pair in training_pairs:
                if direction == "chk_to_en":
                    formatted_pairs.append({
                        'chuukese': pair['chuukese'],
                        'english': pair['english']
                    })
                else:
                    formatted_pairs.append({
                        'english': pair['english'],
                        'chuukese': pair['chuukese']
                    })

            # Retrain model
            success = trainer.fine_tune_model(
                training_pairs=formatted_pairs,
                direction=direction,
                num_epochs=10,  # More epochs for better convergence
                batch_size=8,
                learning_rate=3e-5,  # Slightly lower learning rate
                save_steps=500
            )

            if success:
                self.log(f"✅ {direction.upper()} model retrained successfully")
                return True
            else:
                self.log(f"❌ {direction.upper()} model retraining failed")
                return False

        except Exception as e:
            self.log(f"❌ Error retraining {direction} model: {e}")
            import traceback
            traceback.print_exc()
            return False

    def verify_models(self) -> Dict[str, bool]:
        """Verify that retrained models work correctly"""
        self.log("=== VERIFYING RETRAINED MODELS ===")

        results = {}

        # Test cases for verification
        test_cases = [
            ("chk_to_en", "mwomw", "trust"),  # Should work
            ("chk_to_en", "ran", "water"),   # Should work
            ("en_to_chk", "hello", "aló"),   # May not work yet
            ("en_to_chk", "water", "ran"),   # Should work if trained
        ]

        from transformers import pipeline

        for direction, input_text, expected_contains in test_cases:
            try:

                # Map direction names to actual directory names
                dir_mapping = {
                    "chk_to_en": "helsinki-chuukese_chuukese_to_english",
                    "en_to_chk": "helsinki-chuukese_english_to_chuukese"
                }
                model_dir = dir_mapping.get(direction, f"helsinki-chuukese_{direction}")
                model_path = self.models_dir / f"{model_dir}/finetuned"

                if model_path.exists():
                    model = pipeline('translation', model=str(model_path))
                    result = model(input_text, max_length=128)

                    translation = result[0]['translation_text']
                    success = expected_contains.lower() in translation.lower()

                    results[f"{direction}_{input_text}"] = success
                    self.log(f"✅ {direction}: '{input_text}' -> '{translation}' ({'PASS' if success else 'FAIL'})")
                else:
                    results[f"{direction}_{input_text}"] = False
                    self.log(f"❌ {direction}: Model not found at {model_path}")

            except Exception as e:
                results[f"{direction}_{input_text}"] = False
                self.log(f"❌ {direction}: Verification failed - {e}")

        return results

    def run_full_retraining(self, force: bool = False) -> bool:
        """Run complete retraining pipeline"""
        self.log("="*80)
        self.log("🚀 STARTING COMPLETE MODEL RETRAINING")
        self.log("="*80)

        try:
            # Check if retraining is needed
            if not force and not self.needs_retraining():
                self.log("✅ Models are up to date - no retraining needed")
                return True

            # Prepare training data
            if not self.prepare_training_data():
                return False

            # Retrain both models
            chk_to_en_success = self.retrain_model("chk_to_en")
            en_to_chk_success = self.retrain_model("en_to_chk")

            if not chk_to_en_success or not en_to_chk_success:
                self.log("❌ One or more models failed to retrain")
                return False

            # Verify models
            verification_results = self.verify_models()

            # Summary
            self.log("="*80)
            self.log("📊 RETRAINING SUMMARY")
            self.log("="*80)
            self.log(f"Chuukese→English: {'✅ SUCCESS' if chk_to_en_success else '❌ FAILED'}")
            self.log(f"English→Chuukese: {'✅ SUCCESS' if en_to_chk_success else '❌ FAILED'}")

            passed_tests = sum(verification_results.values())
            total_tests = len(verification_results)
            self.log(f"Verification: {passed_tests}/{total_tests} tests passed")

            success = chk_to_en_success and en_to_chk_success
            self.log(f"Overall: {'✅ SUCCESS' if success else '❌ FAILED'}")
            self.log("="*80)

            return success

        except Exception as e:
            self.log(f"❌ Retraining failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Repeatable Helsinki Model Retraining")
    parser.add_argument("--force", action="store_true", help="Force retraining even if data unchanged")
    parser.add_argument("--verify-only", action="store_true", help="Only run verification, no retraining")

    args = parser.parse_args()

    retrainer = RepeatableModelRetrainer()

    if args.verify_only:
        results = retrainer.verify_models()
        passed = sum(results.values())
        total = len(results)
        print(f"Verification: {passed}/{total} tests passed")
    else:
        success = retrainer.run_full_retraining(force=args.force)
        sys.exit(0 if success else 1)