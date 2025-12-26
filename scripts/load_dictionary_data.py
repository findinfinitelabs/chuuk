#!/usr/bin/env python3
"""
Script to load CSV dictionary data into the database
"""

import sys
import os
import pandas as pd
from datetime import datetime

# Add the project root to sys.path
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')

from src.database.dictionary_db import DictionaryDB

def load_csv_data():
    """Load the CSV dictionary data into the database"""
    
    # Initialize database connection
    dict_db = DictionaryDB()
    
    if not dict_db.client:
        print("❌ Could not connect to database")
        return
    
    print("✅ Connected to database")
    
    # Load CSV file
    csv_path = '/Users/findinfinitelabs/DevApps/chuuk/output/processed_document/CHUUKESE_TO_ENGLISH_dictionary.csv'
    
    try:
        df = pd.read_csv(csv_path)
        print(f"📄 Loaded CSV with {len(df)} entries")
        
        # Clean the data
        entries_added = 0
        
        for _, row in df.iterrows():
            try:
                chuukese_word = str(row.get('Chuukese Word / Form', '')).strip()
                english_def = str(row.get('English Definition', '')).strip()
                part_of_speech = str(row.get('Part of Speech', '')).strip()
                examples = str(row.get('Examples', '')).strip()
                notes = str(row.get('Notes', '')).strip()
                
                # Skip empty entries
                if not chuukese_word or chuukese_word == 'nan' or len(chuukese_word) < 2:
                    continue
                    
                if not english_def or english_def == 'nan' or len(english_def) < 2:
                    continue
                
                # Create dictionary entry
                entry = {
                    'chuukese_word': chuukese_word,
                    'english_translation': english_def,
                    'definition': english_def,
                    'word_type': part_of_speech if part_of_speech and part_of_speech != 'nan' else None,
                    'examples': [examples] if examples and examples != 'nan' else [],
                    'notes': notes if notes and notes != 'nan' else None,
                    'source': 'CSV Import',
                    'created_date': datetime.now()
                }
                
                # Insert into database (avoid duplicates)
                existing = dict_db.dictionary_collection.find_one({
                    'chuukese_word': chuukese_word,
                    'english_translation': english_def
                })
                
                if not existing:
                    dict_db.dictionary_collection.insert_one(entry)
                    entries_added += 1
                    
                    if entries_added % 100 == 0:
                        print(f"📝 Added {entries_added} entries...")
                        
            except Exception as e:
                print(f"⚠️ Error processing row: {e}")
                continue
        
        print(f"🎉 Successfully added {entries_added} dictionary entries to database!")
        
        # Show some stats
        total_count = dict_db.dictionary_collection.count_documents({})
        print(f"📊 Total entries in database: {total_count}")
        
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")

if __name__ == '__main__':
    load_csv_data()