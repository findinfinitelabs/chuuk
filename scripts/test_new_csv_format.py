#!/usr/bin/env python3
"""Debug CSV parsing with the new format:
chuukese_phrase, english_translation, type, direction, definition_notes
"""
import sys
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')

# Test data with new format (tab-separated)
test_csv = """chuukese_phrase	english_translation	type	direction	definition_notes
chómmóng	many	adjective	chk_to_en	Used to describe quantity
aramas	people	noun	chk_to_en	Refers to human beings
Sia tongeni alapaaló ach lúkúlúk	We can build up our trust	phrase	chk_to_en	Common expression about faith
osukosuk	sickness	noun	chk_to_en	General term for illness
Kopwe tongeni filatá	You will be able to decide	sentence	chk_to_en	Future tense expression
Ewe Paipel a áiti ngeni aramas ngeni manawach. Sia tongeni weweiti met a apasa.	The Bible teaches people about life. We can understand what it says.	paragraph	chk_to_en	Sample paragraph from text
"""

print("=" * 60)
print("CSV PARSING DEBUG TEST - NEW FORMAT")
print("=" * 60)
print()
print("Test data:")
print(test_csv)
print()

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Test extraction
print("Testing extraction...")
result = db._extract_entries_from_csv(test_csv, "test_page", "test_pub", "test.tsv")

print(f"\n📊 Total items extracted: {len(result)}")

# Check what's in the collections
word_count = db.dictionary_collection.count_documents({})
phrase_count = db.phrases_collection.count_documents({})
paragraph_count = db.paragraphs_collection.count_documents({})

print(f"\n📚 Database counts:")
print(f"  • Words in dictionary_collection: {word_count}")
print(f"  • Phrases/Sentences in phrases_collection: {phrase_count}")
print(f"  • Paragraphs in paragraphs_collection: {paragraph_count}")

# Show sample entries
print("\n📝 Sample words:")
for entry in db.dictionary_collection.find().limit(3):
    print(f"  • {entry.get('chuukese_word')} = {entry.get('english_translation')} (type: {entry.get('type')}, dir: {entry.get('direction')})")

print("\n💬 Sample phrases/sentences:")
for phrase in db.phrases_collection.find().limit(3):
    chk = phrase.get('chuukese_phrase') or phrase.get('chuukese_sentence', '')
    print(f"  • {chk[:50]}... = {phrase.get('english_translation', '')[:50]}... (type: {phrase.get('type')})")

print("\n📄 Sample paragraphs:")
for para in db.paragraphs_collection.find().limit(2):
    chk = para.get('chuukese_paragraph', '')
    print(f"  • {chk[:60]}... (type: {para.get('type')})")
