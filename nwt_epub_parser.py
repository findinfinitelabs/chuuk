"""
NWT EPUB Parser for extracting Bible verses from JW.org formatted EPUBs
"""
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re
import os

class NWTEpubParser:
    """Parser for NWT (New World Translation) EPUB format"""
    
    def __init__(self, epub_path):
        """Initialize parser with EPUB file path"""
        self.epub_path = epub_path
        self.book = epub.read_epub(epub_path)
        self.book_chapter_map = {}
        self._build_chapter_map()
    
    def _build_chapter_map(self):
        """Build mapping of book names to chapter files by reading TOC"""
        # Read the TOC to build the map
        for item in self.book.get_items():
            if item.get_name() == 'toc.xhtml':
                content = item.get_content()
                soup = BeautifulSoup(content, 'html.parser')
                links = soup.find_all('a', href=True)
                
                current_book = None
                for link in links:
                    text = link.get_text().strip()
                    href = link['href']
                    
                    # Chapter navigation files indicate a book
                    if href.startswith('biblechapternav'):
                        # Extract book number from filename (biblechapternav40.xhtml -> 40)
                        book_num = href.replace('biblechapternav', '').replace('.xhtml', '')
                        if book_num.isdigit():
                            self.book_chapter_map[book_num] = {'name': current_book or text, 'chapters': {}}
                            current_book = book_num
                    else:
                        current_book = text
                
                break
        
        # Now read each chapter navigation to get chapter-to-file mapping
        for item in self.book.get_items():
            if item.get_name().startswith('biblechapternav'):
                book_num = item.get_name().replace('biblechapternav', '').replace('.xhtml', '')
                if book_num in self.book_chapter_map:
                    content = item.get_content()
                    soup = BeautifulSoup(content, 'html.parser')
                    links = soup.find_all('a', href=True)
                    
                    for link in links:
                        text = link.get_text().strip()
                        href = link['href']
                        # Chapter links are numbered
                        if text.isdigit():
                            chapter_num = int(text)
                            self.book_chapter_map[book_num]['chapters'][chapter_num] = href
    
    def get_verse(self, book_num, chapter, verse):
        """
        Extract a specific verse from the EPUB
        
        Args:
            book_num: Book number (1-66, as string or int)
            chapter: Chapter number (int)
            verse: Verse number (int)
        
        Returns:
            str: Verse text, or None if not found
        """
        book_num = str(book_num)
        
        # Get the chapter file
        if book_num not in self.book_chapter_map:
            print(f"Book {book_num} not found in map")
            return None
        
        if chapter not in self.book_chapter_map[book_num]['chapters']:
            print(f"Chapter {chapter} not found for book {book_num}")
            return None
        
        chapter_file = self.book_chapter_map[book_num]['chapters'][chapter]
        
        # Read the chapter file
        for item in self.book.get_items():
            if item.get_name() == chapter_file:
                content = item.get_content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Find the verse marker (id format: chapter{N}_verse{M})
                verse_id = f'chapter{chapter}_verse{verse}'
                verse_marker = soup.find(id=verse_id)
                
                if not verse_marker:
                    return None
                
                # Get the parent paragraph which contains the verse text
                parent = verse_marker.parent
                if not parent:
                    return None
                
                full_text = parent.get_text()
                
                # Extract the specific verse text
                # Pattern: verse number, space, text until next verse number or end
                pattern = rf'{verse}\s+(.+?)(?=\s+{verse+1}\s+|\Z)'
                match = re.search(pattern, full_text, re.DOTALL)
                
                if match:
                    verse_text = match.group(1).strip()
                    # Clean up footnote markers and extra whitespace
                    verse_text = re.sub(r'\*+', '', verse_text)
                    verse_text = re.sub(r'\s+', ' ', verse_text)
                    return verse_text
                
                return None
        
        return None


# Test the parser
if __name__ == '__main__':
    print("=== Testing English Bible ===")
    eng_parser = NWTEpubParser('data/bible/nwt_E.epub')
    print(f"Loaded {len(eng_parser.book_chapter_map)} books")
    
    # Test Genesis 1:1
    verse = eng_parser.get_verse(1, 1, 1)
    print(f"\nGenesis 1:1: {verse}")
    
    # Test John 3:16
    verse = eng_parser.get_verse(43, 3, 16)
    print(f"\nJohn 3:16: {verse}")
    
    print("\n\n=== Testing Chuukese NT ===")
    chk_parser = NWTEpubParser('data/bible/nwt_TE.epub')
    print(f"Loaded {len(chk_parser.book_chapter_map)} books")
    
    # Test Matthew 24:14
    verse = chk_parser.get_verse(40, 24, 14)
    print(f"\nMatthew 24:14: {verse}")
    
    # Test John 3:16
    verse = chk_parser.get_verse(43, 3, 16)
    print(f"\nJohn 3:16: {verse}")
