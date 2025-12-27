import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

# Analyze English Bible structure
print("=== Analyzing English Bible Structure ===\n")
book = epub.read_epub('data/bible/nwt_E.epub')

# Get the navigation/TOC to understand book mapping
nav = None
for item in book.get_items():
    if item.get_name() == 'toc.xhtml':
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        print("TOC structure:")
        links = soup.find_all('a', href=True, limit=10)
        for link in links:
            print(f"  {link.get_text().strip()}: {link['href']}")
        break

# Look for Genesis 1
print("\n=== Looking for Genesis content ===")
for item in book.get_items():
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        content = item.get_content()
        if b'In the beginning God created' in content or b'the heavens and the earth' in content:
            print(f"\nFound in: {item.get_name()}")
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find verses
            verses = soup.find_all(['p', 'div'], class_=re.compile('verse|scrp|bodyTxt'))
            print(f"Found {len(verses)} potential verse elements")
            
            # Show first few
            for i, v in enumerate(verses[:5]):
                data_pid = v.get('data-pid')
                verse_id = v.get('id')
                text = v.get_text().strip()[:100]
                print(f"\n  Element {i}:")
                print(f"    data-pid: {data-pid}")
                print(f"    id: {verse_id}")
                print(f"    class: {v.get('class')}")
                print(f"    text: {text}")
            
            break

# Look for Matthew 24 in Chuukese NT
print("\n\n=== Looking for Matthew 24 in Chuukese NT ===")
book = epub.read_epub('data/bible/nwt_TE.epub')
for item in book.get_items():
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        content = item.get_content()
        # Look for Matthew 24:14 keywords
        if b'Matthew' in content or b'24' in content:
            soup = BeautifulSoup(content, 'html.parser')
            # Check if it has actual verse content
            verses = soup.find_all(['p', 'div'], attrs={'data-pid': True})
            if len(verses) > 5:
                print(f"\nFound in: {item.get_name()}")
                print(f"Found {len(verses)} elements with data-pid")
                
                # Show some verses
                for v in verses[:5]:
                    data_pid = v.get('data-pid')
                    text = v.get_text().strip()[:100]
                    print(f"  data-pid={data_pid}: {text}")
                break
