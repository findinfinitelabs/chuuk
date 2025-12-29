#!/usr/bin/env python3
"""Find actual verse text in Genesis"""

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

book = epub.read_epub('data/bible/old_testament_chuukese.epub')

for item in book.get_items():
    if item.get_name() == 'GEN.xhtml':
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find chapter 1 marker
        chapter1 = soup.find(id='GN1_0')
        if chapter1:
            print('=== Looking for verse text ===')
            
            # Find paragraphs with class 'p'
            verses = soup.find_all('p', class_='p', limit=5)
            for i, verse in enumerate(verses):
                print(f'\n--- Verse paragraph {i+1} ---')
                print(f'Full HTML: {verse}')
                print(f'\nText: {verse.get_text()}')
                
                # Look for verse numbers
                verse_nums = verse.find_all('span', class_='v')
                if verse_nums:
                    print(f'Verse numbers found: {[v.get_text() for v in verse_nums]}')
        break
