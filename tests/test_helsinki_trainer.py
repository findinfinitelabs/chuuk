#!/usr/bin/env python3
"""
Quick test of Helsinki fine-tuning trainer
"""

import os
import sys

# Set environment to prevent Flask from starting
os.environ['SKIP_FLASK_APP'] = '1'

from src.training.helsinki_trainer import HelsinkiFineTuner
from src.database.dictionary_db import DictionaryDB

def test_trainer():
    print("🧪 Testing Helsinki Fine-Tuner")
    print("=" * 60)
    
    # Check database first
    db = DictionaryDB()
    count = db.dictionary_collection.count_documents({})
    print(f"📊 Database has {count} entries")
    
    if count < 10:
        print("⚠️  Warning: Less than 10 entries. Add more data for better results.")
    
    # Create trainer with progress callback
    def progress_callback(stage, progress):
        print(f"  [{int(progress):3d}%] {stage}")
    
    trainer = HelsinkiFineTuner(progress_callback=progress_callback)
    
    # Test data loading
    print("\n📚 Loading training data...")
    training_data = trainer.load_training_data_from_db()
    print(f"✅ Loaded {len(training_data)} training pairs")
    
    if training_data:
        print("\nSample data:")
        for i, pair in enumerate(training_data[:3]):
            print(f"  {i+1}. {pair['chuukese']} → {pair['english']}")
    
    print("\n" + "=" * 60)
    print("✅ Trainer initialized successfully!")
    print("\n💡 To test actual fine-tuning (takes 5-10 minutes):")
    print("   trainer.fine_tune_both_models(num_epochs=1, batch_size=2)")
    print("\n⚠️  Note: Fine-tuning requires significant CPU/GPU resources")
    
    return trainer

if __name__ == "__main__":
    trainer = test_trainer()
