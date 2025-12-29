import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

book = epub.read_epub('data/bible/nwt_E.epub')
for item in book.get_items():
    if item.get_name() == '1001061105.xhtml':
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        
        print("=== Finding Genesis 1:1 ===\n")
        
        # Find the verse marker
        verse_marker = soup.find(id='chapter1_verse1')
        if verse_marker:
            print(f"Found verse marker: {verse_marker.name}, id={verse_marker.get('id')}")
            print(f"Marker text: '{verse_marker.get_text().strip()}'")
            
            # Get text after the marker until next verse
            text_parts = []
            current = verse_marker
            
            # The verse text is often in the same element or parent
            # Look at parent paragraph
            parent = verse_marker.parent
            if parent:
                print(f"\nParent: {parent.name}, data-pid={parent.get('data-pid')}")
                full_text = parent.get_text()
                print(f"Full parent text: {full_text[:200]}")
                
                # Extract just verse 1 (before verse 2)
                # Pattern: verse number followed by text
                match = re.search(r'1\s+(.+?)(?=\s+2\s+|\Z)', full_text, re.DOTALL)
                if match:
                    verse_text = match.group(1).strip()
                    print(f"\n✓ Extracted verse 1: {verse_text}")
        
        # Try another approach - find the span/element containing verse number
        print("\n\n=== Alternative approach - finding verse number span ===")
        # Look for verse number markers
        verse_nums = soup.find_all(class_=re.compile('v|verse'))
        for vn in verse_nums[:5]:
            print(f"{vn.name}.{vn.get('class')}: '{vn.get_text()}'")
        
        break
