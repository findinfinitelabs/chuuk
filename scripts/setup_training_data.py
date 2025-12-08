#!/usr/bin/env python3
"""
Dictionary Training Data Setup
Prepares training data from user dictionaries and JW.org content
"""

import os
import sys
import json
import requests
from pathlib import Path

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.database.dictionary_db import DictionaryDB
from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator

def setup_training_data():
    """Set up training data from all available sources"""
    print("🚀 Setting up Chuukese translation training data...")
    
    # Initialize database
    db = DictionaryDB()
    
    # Initialize Helsinki translator for training
    translator = HelsinkiChuukeseTranslator()
    
    # Load existing dictionary data
    print("📚 Loading dictionary data...")
    data_count = translator.load_dictionary_data()
    print(f"✅ Loaded {data_count} dictionary entries")
    
    # TODO: Add JW.org content fetching
    print("🌐 JW.org content integration (coming soon)")
    
    # Save training data
    training_dir = Path("training_data")
    training_dir.mkdir(exist_ok=True)
    
    if translator.training_data:
        # Save as JSON for inspection
        training_file = training_dir / "chuukese_training_data.json"
        with open(training_file, 'w', encoding='utf-8') as f:
            json.dump([
                {
                    'chuukese': pair.chuukese,
                    'english': pair.english,
                    'source': pair.source
                }
                for pair in translator.training_data
            ], f, ensure_ascii=False, indent=2)
        
        print(f"💾 Training data saved to {training_file}")
        print(f"📊 Total training pairs: {len(translator.training_data)}")
    else:
        print("⚠️ No training data available. Please upload dictionary content first.")

if __name__ == "__main__":
    setup_training_data()
