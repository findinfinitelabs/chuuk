#!/usr/bin/env python3
"""Analyze the Old Testament EPUB structure"""

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

book = epub.read_epub('data/bible/old_testament_chuukese.epub')

# List all items
print('=== EPUB Structure ===')
documents = []
for item in book.get_items():
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        name = item.get_name()
        documents.append(name)
        print(f'Document: {name}')

print(f'\nTotal documents: {len(documents)}')

# Get metadata
print('\n=== Metadata ===')
try:
    print(f'Title: {book.get_metadata("DC", "title")}')
    print(f'Language: {book.get_metadata("DC", "language")}')
except:
    print('Metadata not available')

# Sample first few documents
print('\n=== Sample Content from First 3 Documents ===')
count = 0
for item in book.get_items():
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text()
        
        print(f'\n--- Document: {item.get_name()} ---')
        print(text[:800])
        print('...')
        
        count += 1
        if count >= 3:
            break

# Look for specific patterns in Genesis
print('\n=== Looking for Genesis patterns ===')
for item in book.get_items():
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        name = item.get_name().lower()
        if 'gen' in name or 'genesis' in name or 'chapter' in name or '01' in name:
            content = item.get_content()
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text()
            
            print(f'\n--- Potential Genesis: {item.get_name()} ---')
            print(text[:1000])
            break
