#!/usr/bin/env python3
"""Extract Genesis 1:1 to understand verse structure"""

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

book = epub.read_epub('data/bible/old_testament_chuukese.epub')

# Find Genesis
for item in book.get_items():
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        if item.get_name() == 'GEN.xhtml':
            content = item.get_content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Print raw HTML structure
            print('=== Raw HTML Structure ===')
            print(soup.prettify()[:3000])
            
            # Look for verse patterns
            print('\n\n=== Looking for verse markers ===')
            
            # Try to find chapters and verses
            chapters = soup.find_all('div', class_=lambda x: x and 'chapter' in x.lower() if x else False)
            print(f'Found {len(chapters)} chapter divs')
            
            # Look for any span or div with numbers
            verses = soup.find_all(['span', 'div'], class_=lambda x: x and 'verse' in x.lower() if x else False)
            print(f'Found {len(verses)} verse elements')
            
            # Try to find all span elements with class
            all_spans = soup.find_all('span', class_=True)
            print(f'\nAll spans with class: {len(all_spans)}')
            if all_spans:
                for span in all_spans[:10]:
                    print(f"  Class: {span.get('class')}, Text: {span.get_text()[:100]}")
            
            # Try finding by id
            verse_by_id = soup.find(id='1.1')
            if verse_by_id:
                print(f'\nFound verse by id="1.1": {verse_by_id.get_text()[:200]}')
            
            # Get all text and look for patterns
            text = soup.get_text()
            print('\n=== Full text (first 2000 chars) ===')
            print(text[:2000])
            
            break
