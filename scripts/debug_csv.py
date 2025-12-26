#!/usr/bin/env python3
"""Debug script to test CSV parsing"""
import sys
import os
import csv
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Read the TSV file
with open('chuukese_phrase_book.tsv', 'r', encoding='utf-8') as f:
    csv_content = f.read()

print("="*60)
print("CSV PARSING DEBUG TEST")
print("="*60)

print(f"\n📄 File content length: {len(csv_content)} characters")
print(f"📄 First 500 chars:\n{csv_content[:500]}")

# Parse as TSV
csv_reader = csv.reader(io.StringIO(csv_content), delimiter='\t')

# Read header
header = next(csv_reader, None)
if header:
    print(f"\n📋 Header columns: {len(header)}")
    print(f"📋 Headers: {header}")
    header_lower = [h.lower().strip() for h in header]
    print(f"📋 Normalized: {header_lower}")
    print(f"📋 First header: '{header_lower[0]}'")
    print(f"📋 'chuukese word' in first header: {'chuukese word' in header_lower[0]}")
else:
    print("❌ No header found!")
    sys.exit(1)

# Read first few rows
print("\n📝 First 5 data rows:")
for i, row in enumerate(csv_reader):
    if i >= 5:
        break
    print(f"  Row {i+2}: {len(row)} cols - {row[:3]}...")

print("\n" + "="*60)
print("Testing full extraction...")
print("="*60)

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Simulate extraction
entries = db._extract_entries_from_csv(csv_content, "test_page", "test_pub", "test.tsv")
print(f"\n✅ Extracted {len(entries)} entries")

if entries:
    print("\n📖 First 3 entries:")
    for e in entries[:3]:
        print(f"  • {e.get('chuukese_word')} = {e.get('english_translation')[:50]}...")
