import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

# Check what's in the first content file
print("=== English Bible - First content file ===")
book = epub.read_epub('data/bible/nwt_E.epub')
for item in book.get_items():
    if item.get_name() == '1001061101.xhtml':
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        print(soup.prettify()[:2000])
        break

print("\n\n=== Chuukese NT - Looking for actual chapter files ===")
book = epub.read_epub('data/bible/nwt_TE.epub')
for item in book.get_items():
    if '40' in item.get_name() and item.get_type() == ebooklib.ITEM_DOCUMENT:
        print(f"\nFile: {item.get_name()}")
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        # Look for chapter/verse markers
        ids = [elem.get('id') for elem in soup.find_all(id=True)][:20]
        print(f"IDs: {ids}")
        # Show some text
        paras = soup.find_all('p', limit=3)
        for p in paras:
            text = p.get_text()[:150]
            if text.strip():
                print(f"Text: {text}")
                break
        break
