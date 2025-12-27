#!/usr/bin/env python3
import ebooklib
from ebooklib import epub  
from bs4 import BeautifulSoup

book = epub.read_epub('data/bible/old_testament_chuukese.epub')

for item in book.get_items():
    if item.get_name() == 'GEN.xhtml':
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all elements with IDs
        elements_with_id = soup.find_all(id=True)
        print('IDs found in Genesis:')
        for elem in elements_with_id[:15]:
            print(f'  {elem.get("id")}')
        break
