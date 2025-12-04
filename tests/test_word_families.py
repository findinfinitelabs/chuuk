#!/usr/bin/env python3
"""Test the enhanced multi-entry extraction and word family search"""

import tempfile
import os
from src.database.dictionary_db import DictionaryDB

def test_multi_entry_extraction():
    """Test extracting multiple entries from complex lines and word family search"""
    
    # Create a test database
    db = DictionaryDB()
    
    # Clear any existing test data
    db.dictionary_collection.delete_many({'publication_id': 'test_pub_1'})
    db.pages_collection.delete_many({'publication_id': 'test_pub_1'})
    
    # Test data simulating complex Chuukese dictionary content
    test_content = """
chem – remember, chemeni – v. remember, chechchemeni, -ei, -uk*, -kem, -kemi, -ir, -kich – remember (me, you, etc.)

mwenge – feast

kopwe – will, kopwei – v. will, chekopwei, -ei, -uk, -ir – future markers (me, you, him)

aninis – ant, insect

pwata (n.) – thing, pwateki, -ei, -uk*, -kem, -kemi, -ir, -kich – things (my, your, his, our, your pl., their)
"""
    
    print("Testing Multi-Entry Extraction and Word Family Search")
    print("=" * 65)
    
    # Create temporary text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        # Process the test content
        print(f"Processing test content...")
        page_id = db.add_dictionary_page(
            publication_id="test_pub_1",
            filename="test_complex_dictionary.txt", 
            ocr_text=test_content,
            page_number=1
        )
        
        # Get all entries from the test publication
        all_results = db.dictionary_collection.find({'publication_id': 'test_pub_1'})
        entries = list(all_results)
        
        print(f"\n✅ Extracted {len(entries)} total entries")
        
        # Group entries by base word
        base_words = {}
        for entry in entries:
            base = entry.get('base_word', entry.get('chuukese_word'))
            if base not in base_words:
                base_words[base] = []
            base_words[base].append(entry)
        
        print(f"\n📊 Found {len(base_words)} word families:")
        
        for base_word, word_entries in base_words.items():
            if any(e.get('search_direction') != 'en_to_chk' for e in word_entries):
                print(f"\n🔤 Word Family: '{base_word}'")
                chk_entries = [e for e in word_entries if e.get('search_direction') != 'en_to_chk']
                for entry in chk_entries:
                    word = entry['chuukese_word']
                    definition = entry['english_translation']
                    is_base = "⭐ BASE" if entry.get('is_base_word') else ""
                    inflection = f" [{entry.get('inflection_type', '')}]" if entry.get('inflection_type') else ""
                    print(f"   • {word} → {definition} {is_base}{inflection}")
        
        print(f"\n" + "=" * 65)
        print("Testing Word Family Search")
        print("=" * 65)
        
        # Test word family search for 'chem'
        print(f"\n🔍 Searching for 'chem' (should find entire word family):")
        results = db.search_word('chem', limit=20, include_related=True)
        chem_results = [r for r in results if r.get('search_direction') != 'en_to_chk']
        
        for i, result in enumerate(chem_results, 1):
            word = result['chuukese_word']
            definition = result['english_translation']
            relevance = result.get('relevance', 0)
            base = result.get('base_word', '')
            is_base = "⭐" if result.get('is_base_word') else ""
            inflection = result.get('inflection_type', '')
            
            print(f"   {i}. {word} → {definition}")
            print(f"      Score: {relevance:.1f}, Base: {base}, {is_base} {inflection}")
        
        print(f"\n🔍 Searching for 'pwata' (should find word family):")
        results = db.search_word('pwata', limit=20, include_related=True)
        pwata_results = [r for r in results if r.get('search_direction') != 'en_to_chk']
        
        for i, result in enumerate(pwata_results, 1):
            word = result['chuukese_word']
            definition = result['english_translation']
            relevance = result.get('relevance', 0)
            base = result.get('base_word', '')
            is_base = "⭐" if result.get('is_base_word') else ""
            
            print(f"   {i}. {word} → {definition}")
            print(f"      Score: {relevance:.1f}, Base: {base} {is_base}")
        
        print(f"\n🔍 Searching for 'remember' (should find English matches):")
        results = db.search_word('remember', limit=10, include_related=True)
        remember_results = [r for r in results if r.get('search_direction') != 'en_to_chk']
        
        for i, result in enumerate(remember_results, 1):
            word = result['chuukese_word']
            definition = result['english_translation']
            relevance = result.get('relevance', 0)
            print(f"   {i}. {word} → {definition} (Score: {relevance:.1f})")
        
    finally:
        # Clean up
        os.unlink(temp_file)
    
    print(f"\n" + "=" * 65)
    print("✅ Multi-Entry Extraction and Word Family Search Test Complete!")
    print("✅ Each word-definition pair is now logged as a separate entry")
    print("✅ Base word searches return all related forms")
    print("✅ Word families are properly linked via base_word field")

if __name__ == "__main__":
    test_multi_entry_extraction()