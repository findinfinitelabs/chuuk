"""
Search the Chuukese NWT EPUB for dictionary words and find all scriptures containing them.
Sample: search for 'aal' and 'allach'
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString
import json

# NWT book number -> English name mapping (standard 1-66)
BOOK_NAMES = {
    1: "Genesis", 2: "Exodus", 3: "Leviticus", 4: "Numbers", 5: "Deuteronomy",
    6: "Joshua", 7: "Judges", 8: "Ruth", 9: "1 Samuel", 10: "2 Samuel",
    11: "1 Kings", 12: "2 Kings", 13: "1 Chronicles", 14: "2 Chronicles",
    15: "Ezra", 16: "Nehemiah", 17: "Esther", 18: "Job", 19: "Psalms",
    20: "Proverbs", 21: "Ecclesiastes", 22: "Song of Solomon", 23: "Isaiah",
    24: "Jeremiah", 25: "Lamentations", 26: "Ezekiel", 27: "Daniel",
    28: "Hosea", 29: "Joel", 30: "Amos", 31: "Obadiah", 32: "Jonah",
    33: "Micah", 34: "Nahum", 35: "Habakkuk", 36: "Zephaniah",
    37: "Haggai", 38: "Zechariah", 39: "Malachi",
    40: "Matthew", 41: "Mark", 42: "Luke", 43: "John", 44: "Acts",
    45: "Romans", 46: "1 Corinthians", 47: "2 Corinthians", 48: "Galatians",
    49: "Ephesians", 50: "Philippians", 51: "Colossians",
    52: "1 Thessalonians", 53: "2 Thessalonians", 54: "1 Timothy",
    55: "2 Timothy", 56: "Titus", 57: "Philemon", 58: "Hebrews",
    59: "James", 60: "1 Peter", 61: "2 Peter", 62: "1 John",
    63: "2 John", 64: "3 John", 65: "Jude", 66: "Revelation"
}


def extract_all_verses(epub_path):
    """Extract all verses from the Chuukese NWT EPUB.
    
    The EPUB uses biblechapternav{book_num}.xhtml files that link to
    content files like 1001061144.xhtml (ch1) and 1001061144-split{N}.xhtml (ch N).
    Verses are marked with <span id="chapter{C}_verse{V}"> and the text
    runs until the next verse marker within the same <p> block.
    """
    book = epub.read_epub(epub_path)
    
    # Step 1: Build book_num -> {book_name, chapter_files} from biblechapternav files
    book_map = {}  # {book_num: {name, chapters: {ch_num: filename}}}
    for item in book.get_items():
        name = item.get_name()
        m = re.match(r'biblechapternav(\d+)\.xhtml', name)
        if not m:
            continue
        book_num = int(m.group(1))
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        book_name = soup.get_text().strip().split('\n')[0].strip()
        
        chapters = {}
        for link in soup.find_all('a', href=True):
            ch_text = link.get_text().strip()
            if ch_text.isdigit():
                chapters[int(ch_text)] = link['href']
        
        book_map[book_num] = {'name': book_name, 'chapters': chapters}
    
    # Step 2: Build set of content filenames we care about, mapped to (book_num, chapter_num)
    file_to_book_ch = {}  # {filename: (book_num, chapter_num)}
    for book_num, info in book_map.items():
        for ch_num, filename in info['chapters'].items():
            file_to_book_ch[filename] = (book_num, ch_num)
    
    # Step 3: Extract verses from content files
    verses = []
    for item in book.get_items():
        fname = item.get_name()
        if fname not in file_to_book_ch:
            continue
        
        book_num, chapter_num = file_to_book_ch[fname]
        content = item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all verse markers in this file
        verse_markers = soup.find_all(id=re.compile(r'^chapter\d+_verse\d+$'))
        
        for i, marker in enumerate(verse_markers):
            vid = marker.get('id', '')
            vm = re.match(r'chapter(\d+)_verse(\d+)', vid)
            if not vm:
                continue
            ch = int(vm.group(1))
            vn = int(vm.group(2))
            
            # Collect text from this marker until the next verse marker
            # Walk siblings after the marker within the same parent <p>
            text_parts = []
            node = marker.next_sibling
            while node:
                # Stop if we hit another verse marker
                if hasattr(node, 'get') and node.get('id', '').startswith('chapter') and '_verse' in node.get('id', ''):
                    break
                if isinstance(node, NavigableString):
                    text_parts.append(str(node))
                elif hasattr(node, 'get_text'):
                    # Skip footnote links (the * markers)
                    if node.name == 'a' and node.get('epub:type') == 'noteref':
                        pass
                    elif node.get('id', '').startswith('footnotesource'):
                        pass
                    else:
                        text_parts.append(node.get_text())
                node = node.next_sibling
            
            verse_text = ' '.join(text_parts)
            verse_text = re.sub(r'\*+', '', verse_text)
            verse_text = re.sub(r'\s+', ' ', verse_text).strip()
            
            if verse_text:
                verses.append((book_num, ch, vn, verse_text))
    
    return verses, book_map


def search_word_in_verses(verses, book_map, word):
    """Search for a Chuukese word in all verses (word boundary match).
    Uses a custom boundary pattern since \\b doesn't handle accented Chuukese chars."""
    # Chuukese letter class for word boundaries (includes accented vowels)
    chk = r'[a-záàâäéèêëíìîïóòôöúùûüñčšž]'
    pattern = re.compile(rf'(?<!{chk[1:-1]}){re.escape(word)}(?!{chk[1:-1]})', re.IGNORECASE)
    results = []
    seen = set()
    for book_num, ch, vn, text in verses:
        key = (book_num, ch, vn)
        if key in seen:
            continue
        if pattern.search(text):
            seen.add(key)
            # Use Chuukese book name from EPUB, with English in parens
            chk_name = book_map.get(book_num, {}).get('name', f'Book {book_num}')
            eng_name = BOOK_NAMES.get(book_num, '')
            display = f"{chk_name} ({eng_name})" if eng_name else chk_name
            results.append({
                'reference': f"{display} {ch}:{vn}",
                'book_num': book_num,
                'chapter': ch,
                'verse': vn,
                'text': text
            })
    return results


if __name__ == '__main__':
    epub_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             'config', 'data', 'bible', 'nwt_TE.epub')
    
    words_to_search = sys.argv[1:] if len(sys.argv) > 1 else ['aal', 'allach']
    
    print(f"📖 Loading Chuukese NWT EPUB: {epub_path}")
    verses, book_map = extract_all_verses(epub_path)
    print(f"✅ Extracted {len(verses)} verses from {len(book_map)} books\n")
    
    for word in words_to_search:
        print(f"{'='*60}")
        print(f"🔍 Searching for: '{word}'")
        print(f"{'='*60}")
        results = search_word_in_verses(verses, book_map, word)
        
        if results:
            print(f"Found {len(results)} scripture(s):\n")
            for r in results:
                print(f"  📗 {r['reference']}")
                highlighted = re.sub(
                    rf'(?<![a-záàâäéèêëíìîïóòôöúùûüñčšž]){re.escape(word)}(?![a-záàâäéèêëíìîïóòôöúùûüñčšž])', 
                    lambda m: f"**{m.group()}**", 
                    r['text'], 
                    flags=re.IGNORECASE
                )
                print(f"     {highlighted}\n")
        else:
            print(f"  No scriptures found containing '{word}'\n")
