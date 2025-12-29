import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

# Check the chapter navigation files
print("=== Checking Genesis Chapter Navigation ===")
book = epub.read_epub('data/bible/nwt_E.epub')
for item in book.get_items():
    if item.get_name() == 'biblechapternav1.xhtml':
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        links = soup.find_all('a', href=True)
        print(f"Found {len(links)} chapter links")
        for link in links[:10]:
            print(f"  Chapter {link.get_text().strip()}: {link['href']}")
        break

# Now check one of those chapter files
print("\n=== Checking Genesis Chapter 1 ===")
for item in book.get_items():
    # Genesis chapter 1 should be in one of the numbered files
    if '1001061001' in item.get_name():
        print(f"Checking: {item.get_name()}")
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Look for verse markers
        # Try different patterns
        verses_with_pid = soup.find_all(attrs={'data-pid': True})
        print(f"Elements with data-pid: {len(verses_with_pid)}")
        
        for v in verses_with_pid[:10]:
            print(f"  {v.name} data-pid={v.get('data-pid')}, id={v.get('id')}")
            print(f"    text: {v.get_text().strip()[:80]}")

# Check all files starting with 100106100
print("\n=== All files starting with 100106100 ===")
for item in book.get_items():
    if item.get_name().startswith('100106100') and item.get_type() == ebooklib.ITEM_DOCUMENT:
        print(f"  {item.get_name()}")
        content = item.get_content()
        # Check if it has "In the beginning"
        if b'In the beginning' in content:
            print(f"    ^^ Contains Genesis 1:1 text!")
