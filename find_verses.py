#!/usr/bin/env python3
"""Find verse structure in Genesis"""

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
            print('Found chapter 1 marker')
            print('Element:', chapter1.name)
            
            # Get parent and look for verses
            parent = chapter1.parent
            print(f'\nParent: {parent.name}, class={parent.get("class")}')
            
            # Find all paragraphs after chapter marker
            verses = chapter1.find_all_next('p', limit=10)
            for i, verse in enumerate(verses):
                print(f'\n--- Paragraph {i+1} ---')
                print(f'Class: {verse.get("class")}')
                print(f'ID: {verse.get("id")}')
                print(f'Text: {verse.get_text()[:200]}')
                
                # Check for spans inside
                spans = verse.find_all('span')
                if spans:
                    print(f'  Contains {len(spans)} spans:')
                    for span in spans[:3]:
                        print(f'    Span class={span.get("class")}, text={span.get_text()[:50]}')
        break
