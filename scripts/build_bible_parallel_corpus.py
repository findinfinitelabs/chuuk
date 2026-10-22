#!/usr/bin/env python3
"""
Build a parallel Chuukese<->English sentence corpus from the NWT Bible EPUBs.

The dictionary corpus is overwhelmingly single words, so the fine-tuned Helsinki
models handle vocabulary well but fall apart on full sentences. The NWT is the
largest aligned Chuukese/English text available to us, so it is the practical
source of sentence-level training signal.

`NWTEpubParser.get_verse` re-scans every EPUB item and re-parses the chapter
XHTML on each call, which is fine for a verse-preview popup but far too slow for
a whole-Bible sweep. This script keeps the parser's chapter map and does its own
chapter-at-a-time extraction with the soup cached.

Run from project root:
    .venv/bin/python scripts/build_bible_parallel_corpus.py [--output PATH] [--max-verses N]
"""

import re
import sys
import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bs4 import BeautifulSoup  # noqa: E402

from src.utils.nwt_epub_parser import NWTEpubParser  # noqa: E402

CHK_EPUB = "config/data/bible/nwt_TE.epub"
EN_EPUB = "config/data/bible/nwt_E.epub"

# A chapter ends when we stop finding verses; a couple of misses in a row can be
# legitimate gaps (verses omitted in the NWT, e.g. Matthew 17:21), so only give
# up after several consecutive misses.
MAX_CONSECUTIVE_MISSES = 4

# Guards against misaligned pairs: a Chuukese verse and its English counterpart
# are never wildly different in length.
MIN_CHARS = 8
MAX_CHARS = 600
MIN_LEN_RATIO = 0.4
MAX_LEN_RATIO = 2.5


def clean(text: str) -> str:
    """Strip JW footnote/cross-reference markers and normalise whitespace."""
    text = re.sub(r"[*+]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class ChapterExtractor:
    """Pulls every verse out of a chapter in one parse."""

    def __init__(self, epub_path: str):
        self.parser = NWTEpubParser(epub_path)
        self.book_chapter_map = self.parser.book_chapter_map
        # name -> item, so a chapter lookup is a dict hit rather than a scan
        self._items = {item.get_name(): item for item in self.parser.book.get_items()}
        self._soup_cache: dict = {}

    def _soup(self, chapter_file: str):
        if chapter_file not in self._soup_cache:
            item = self._items.get(chapter_file)
            if item is None:
                self._soup_cache[chapter_file] = None
            else:
                self._soup_cache[chapter_file] = BeautifulSoup(item.get_content(), "html.parser")
        return self._soup_cache[chapter_file]

    def chapter_verses(self, book_num: str, chapter: int, max_verses: int) -> dict:
        """Return {verse_num: text} for one chapter."""
        book = self.book_chapter_map.get(book_num)
        if not book or chapter not in book["chapters"]:
            return {}

        soup = self._soup(book["chapters"][chapter])
        if soup is None:
            return {}

        verses = {}
        misses = 0
        for verse in range(1, max_verses + 1):
            marker = soup.find(id=f"chapter{chapter}_verse{verse}")
            parent = marker.parent if marker else None
            text = None
            if parent:
                # Same extraction shape as NWTEpubParser.get_verse: the verse
                # number introduces its text and runs until the next number.
                full_text = parent.get_text()
                match = re.search(rf"{verse}\s+(.+?)(?=\s+{verse + 1}\s+|\Z)", full_text, re.DOTALL)
                if match:
                    text = clean(match.group(1))

            if text:
                verses[verse] = text
                misses = 0
            else:
                misses += 1
                if misses >= MAX_CONSECUTIVE_MISSES:
                    break

        # Free the chapter as soon as we're done with it — the full NWT soup set
        # does not need to stay resident.
        self._soup_cache.pop(book["chapters"][chapter], None)
        return verses


def acceptable(chk: str, eng: str) -> bool:
    if not (MIN_CHARS <= len(chk) <= MAX_CHARS and MIN_CHARS <= len(eng) <= MAX_CHARS):
        return False
    ratio = len(chk) / len(eng)
    return MIN_LEN_RATIO <= ratio <= MAX_LEN_RATIO


def main():
    parser = argparse.ArgumentParser(description="Build parallel Bible corpus from NWT EPUBs")
    parser.add_argument("--output", default="training_data/bible_parallel.json")
    parser.add_argument("--max-verses", type=int, default=180, help="Highest verse number to probe per chapter")
    parser.add_argument("--chk-epub", default=CHK_EPUB)
    parser.add_argument("--en-epub", default=EN_EPUB)
    args = parser.parse_args()

    print(f"📖 Loading Chuukese EPUB: {args.chk_epub}")
    chk = ChapterExtractor(args.chk_epub)
    print(f"📖 Loading English EPUB:  {args.en_epub}")
    eng = ChapterExtractor(args.en_epub)

    shared_books = sorted(
        set(chk.book_chapter_map) & set(eng.book_chapter_map),
        key=lambda b: int(b),
    )
    print(f"📚 Books in both editions: {len(shared_books)}")

    pairs = []
    skipped = 0
    for book_num in shared_books:
        chk_book = chk.book_chapter_map[book_num]
        eng_book = eng.book_chapter_map[book_num]
        chapters = sorted(set(chk_book["chapters"]) & set(eng_book["chapters"]))
        book_pairs = 0

        for chapter in chapters:
            chk_verses = chk.chapter_verses(book_num, chapter, args.max_verses)
            if not chk_verses:
                continue
            eng_verses = eng.chapter_verses(book_num, chapter, args.max_verses)

            for verse, chk_text in sorted(chk_verses.items()):
                eng_text = eng_verses.get(verse)
                if not eng_text:
                    skipped += 1
                    continue
                if not acceptable(chk_text, eng_text):
                    skipped += 1
                    continue
                pairs.append(
                    {
                        "chuukese": chk_text,
                        "english": eng_text,
                        "reference": f"{chk_book['name']} {chapter}:{verse}",
                        "source": "nwt_bible",
                    }
                )
                book_pairs += 1

        print(f"   {book_num:>2} {chk_book['name']:<28} {book_pairs:>5} verses")

    out_path = PROJECT_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pairs, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(pairs):,} parallel verses written → {args.output}")
    print(f"   Skipped (missing counterpart or failed length check): {skipped:,}")
    if pairs:
        print("\nSample:")
        for p in pairs[:3]:
            print(f"   [{p['reference']}]")
            print(f"      CHK: {p['chuukese'][:100]}")
            print(f"      EN : {p['english'][:100]}")


if __name__ == "__main__":
    main()
