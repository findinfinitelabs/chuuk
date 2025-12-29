#!/usr/bin/env python3
"""Test extracting Genesis 1:1"""

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

def extract_ot_verse(book_code, chapter, verse):
    """Extract a verse from Old Testament EPUB"""
    book = epub.read_epub('data/bible/old_testament_chuukese.epub')
    
    # Book code mapping (2-letter codes used in EPUB)
    book_codes = {
        'Genesis': 'GN', 'Exodus': 'EX', 'Leviticus': 'LV', 'Numbers': 'NU', 'Deuteronomy': 'DT',
        'Joshua': 'JS', 'Judges': 'JG', 'Ruth': 'RT', '1 Samuel': '1S', '2 Samuel': '2S',
        '1 Kings': '1K', '2 Kings': '2K', '1 Chronicles': '1C', '2 Chronicles': '2C', 'Ezra': 'ER',
        'Nehemiah': 'NE', 'Esther': 'ET', 'Job': 'JB', 'Psalms': 'PS', 'Proverbs': 'PR',
        'Ecclesiastes': 'EC', 'Song of Solomon': 'SS', 'Isaiah': 'IS', 'Jeremiah': 'JR', 'Lamentations': 'LM',
        'Ezekiel': 'EK', 'Daniel': 'DN', 'Hosea': 'HS', 'Joel': 'JL', 'Amos': 'AM',
        'Obadiah': 'OB', 'Jonah': 'JN', 'Micah': 'MC', 'Nahum': 'NM', 'Habakkuk': 'HK',
        'Zephaniah': 'ZP', 'Haggai': 'HG', 'Zechariah': 'ZC', 'Malachi': 'ML'
    }
    
    book_abbrev = book_codes.get(book_code, book_code)
    filename = f'{book_abbrev.upper() if len(book_abbrev) == 2 else book_abbrev}.xhtml'
    
    # Map common abbreviations
    if book_code.upper() in ['GEN', 'GENESIS']: book_abbrev = 'GN'
    elif book_code.upper() in ['EXO', 'EXODUS', 'EXOD']: book_abbrev = 'EX'
    elif book_code.upper() in ['LEV', 'LEVITICUS']: book_abbrev = 'LV'
    
    # Filenames are like GEN.xhtml, EXO.xhtml
    file_mapping = {
        'GN': 'GEN', 'EX': 'EXO', 'LV': 'LEV', 'NU': 'NUM', 'DT': 'DEU'
    }
    filename = f'{file_mapping.get(book_abbrev, book_abbrev.upper())}.xhtml'
    
    print(f"Looking for file: {filename}, ID: {book_abbrev}{chapter}_{verse}")
    
    for item in book.get_items():
        if item.get_name() == filename:
            print(f"Found book file: {filename}")
            content = item.get_content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find verse by ID (e.g., GN1_1 for Genesis 1:1)
            verse_id = f'{book_abbrev}{chapter}_{verse}'
            verse_elem = soup.find(id=verse_id)
            
            if not verse_elem:
                print(f"Verse element not found: {verse_id}")
                return None
            
            print(f"Found verse element: {verse_id}")
            
            # The verse element is a span with the verse number
            # The verse text comes after it until the next verse marker
            verse_text_parts = []
            current = verse_elem.next_sibling
            
            # Get all text until we hit another verse marker (span with id ending in underscore+number)
            while current:
                if hasattr(current, 'name') and current.name == 'span' and current.get('id'):
                    # Check if this is another verse marker (has underscore+number pattern)
                    if re.match(r'^[A-Z0-9]+_\d+$', current.get('id', '')):
                        break
                
                if hasattr(current, 'get_text'):
                    verse_text_parts.append(current.get_text())
                elif isinstance(current, str):
                    verse_text_parts.append(current)
                
                current = current.next_sibling if hasattr(current, 'next_sibling') else None
            
            verse_text = ''.join(verse_text_parts).strip()
            
            # Clean up cross-references and extra whitespace
            verse_text = re.sub(r'✡.*?(?=\n|$)', '', verse_text, flags=re.MULTILINE)
            verse_text = re.sub(r'\s+', ' ', verse_text)  # Normalize whitespace
            verse_text = verse_text.strip()
            
            return verse_text
    
    print(f"Book file not found: {filename}")
    return None

# Test
print("Testing Genesis 1:1")
verse = extract_ot_verse('GEN', 1, 1)
print(f"Result: {verse}")

print("\nTesting Genesis 1:2")
verse = extract_ot_verse('GEN', 1, 2)
print(f"Result: {verse}")

print("\nTesting Exodus 20:13")
verse = extract_ot_verse('EXO', 20, 13)
print(f"Result: {verse}")
