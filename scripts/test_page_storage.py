#!/usr/bin/env python3
"""Test script to verify pages are stored in database during upload"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

print("="*60)
print("DATABASE PAGE STORAGE TEST")
print("="*60)

# Check pages collection
page_count = db.pages_collection.count_documents({})
print(f"\nTotal pages in database: {page_count}")

if page_count > 0:
    print("\nRecent pages:")
    pages = list(db.pages_collection.find().limit(10))
    for page in pages:
        pub_id = page.get('publication_id', 'N/A')
        filename = page.get('filename', 'N/A')
        page_num = page.get('page_number', 'N/A')
        entries = page.get('entries_extracted', 0)
        has_text = bool(page.get('ocr_text'))
        print(f"  • {pub_id} - {filename} (Page {page_num})")
        print(f"    Entries: {entries}, Has OCR text: {has_text}")
else:
    print("\n⚠️  No pages found in database!")
    print("    When you upload a document with 'Index Dictionary' checked,")
    print("    pages should be stored in the pages_collection.")

# Check dictionary entries collection
from pymongo import DESCENDING
try:
    entry_count = db.dictionary_collection.count_documents({})
    print(f"\nTotal dictionary entries: {entry_count}")
    
    if entry_count > 0:
        print("\nRecent entries:")
        entries = list(db.dictionary_collection.find().limit(5))
        for entry in entries:
            word = entry.get('headword', 'N/A')
            translation = entry.get('translation', 'N/A')
            word_type = entry.get('type', 'N/A')
            print(f"  • {word} ({word_type}) = {translation}")
except Exception as e:
    print(f"\n⚠️  Error checking entries: {e}")

print("\n" + "="*60)
