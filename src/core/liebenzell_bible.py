"""
The Liebenzell Mission Chuukese Bible ("Paipel", © 1984–2001 Liebenzell
Mission, CC BY-ND 4.0), read from its PDF.

The New World Translation in Chuukese covers only Matthew–Revelation on
wol.jw.org, so for a Hebrew Scriptures citation (Genesis–Malachi) the Talk
Builder shows this translation instead, clearly labelled: it is a different
translation, not the one the talk is quoting.

Page layout the parser relies on (pypdf text):

    KENESES 1:3 2 KENESES 1:28          page header: book c:v, page, book c:v
    3                                   a bare number opens a chapter
    Än ekewe aramas sosot me ar tur     section heading(s) …
    3.1-24                              … closed by a verse-range line
    1 Iwe, ewe serepenit a …            verse lines start with their number
    Lapalap a föriir. …                 continuation lines do not
    ✡ 2:2: Ipr 4.4,10 ✡ 2:3: …          footnotes close the page

Single-chapter books carry "OPATAIA1" in the header (no colon) and no bare
chapter line. Each book opens with an introduction ("Kapas akom") that is
skipped: verses start only after the first range line of the book.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Book labels as the page headers print them, in canonical order (1–66).
BOOK_LABELS = [
    "KENESES", "EKISTOS", "LIFITIKOS", "NUMPERIS", "TUTERONOMI", "JOSUA", "SOUKAPWÜNG", "RUT",
    "1.SAMUEL", "2.SAMUEL", "1.KING", "2.KING", "1.KRONIKA", "2.KRONIKA", "ESRA", "NEHEMIA", "ESTER",
    "HIOP", "KÖLFEL", "ÄN SALOMON FOS (PROFERPIS)", "ÄN SALOMON AFALAFAL", "ÄN SALOMON KÖL", "AISEA",
    "JEREMAIA", "KÖLÜN KECHÜ", "ISIKIEL", "TANIEL", "OSEA", "SOWEL", "AMOS", "OPATAIA", "SONA", "MIKA",
    "NAHUM", "APAKUK", "SEFANAIA", "AKAI", "SEKARAIA", "MALAKAI",
    "MATEUS", "MARKUS", "LUKAS", "JOHANNES", "FÖFÖR", "ROM", "1 KORINT", "2 KORINT", "KALATIA", "EFISOS",
    "FILIPI", "KOLOSE", "1 TESALONIKA", "2 TESALONIKA", "1 TIMOTY", "2 TIMOTY", "TITUS", "FILIMON", "IPRU",
    "JAMES", "1 PETRUS", "2 PETRUS", "1 JOHANNES", "2 JOHANNES", "3 JOHANNES", "JUTAS", "PWÄRÄTÄ",
]
SOURCE = "Liebenzell Mission Paipel (1984–2001)"
DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "bible" / "liebenzell_chk_ot.json"
COLLECTION = "bible_chapters"
LANG = "chk_lm"

_HEADER = re.compile(r"^(.*?)\s*(\d+)(?::(\d+))?\s+\d+\s+")
_RANGE = re.compile(r"^\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?$|^\d+\.\d+$")
_VERSE = re.compile(r"^(\d+)\s+(\S.*)$")
_FOOTNOTE = "✡"
# A footnote line: marker, then the verse it belongs to ("✡ 2:2: Ipr 4.4,10", "† 3:24: …").
_FOOTNOTE_LINE = re.compile(r"^[✡†*‡§]+\s*\d+[:.]\d+")


def _norm(label: str) -> str:
    return re.sub(r"[\s.]", "", label.upper())


_BOOK_INDEX = {_norm(l): i + 1 for i, l in enumerate(BOOK_LABELS)}


def book_number(label: str) -> int | None:
    return _BOOK_INDEX.get(_norm(label))


class _Parser:
    def __init__(self):
        self.bible: dict[int, dict[int, dict[int, str]]] = {}
        self.book = None
        self.chapter = None
        self.verse = 0
        self.armed = False  # a range line has been seen for this book
        self.buffer: list[str] = []  # unnumbered lines not yet assigned

    def _append_to_verse(self, text: str):
        if self.book and self.chapter and self.verse:
            ch = self.bible[self.book][self.chapter]
            ch[self.verse] = (ch[self.verse] + " " + text).strip()

    def _flush(self):
        for line in self.buffer:
            self._append_to_verse(line)
        self.buffer = []

    def page(self, text: str):
        lines = [l.strip() for l in text.split("\n")]
        lines = [l for l in lines if l]
        if not lines:
            return
        m = _HEADER.match(lines[0])
        if m and book_number(m.group(1)):
            book = book_number(m.group(1))
            if book != self.book:
                self._flush()
                self.book, self.chapter, self.verse, self.armed = book, None, 0, False
                self.bible.setdefault(book, {})
            lines = lines[1:]
        if self.book is None:
            return
        for raw in lines:
            if _FOOTNOTE_LINE.match(raw):
                break  # footnotes run to the end of the page
            line = re.sub(r"[✡†*‡§]", "", raw).strip()
            if not line:
                continue
            if _RANGE.match(line):
                self.buffer = []  # headings before a range are section titles
                self.armed = True
                continue
            if line.isdigit():
                n = int(line)
                if self.chapter is not None and n == self.chapter + 1:
                    self._flush()
                    self.chapter, self.verse = n, 0
                    self.bible[self.book].setdefault(n, {})
                    continue
                if self.chapter is None and n == 1:
                    continue
                self.buffer.append(line)
                continue
            vm = _VERSE.match(line)
            if vm and self.armed:
                n = int(vm.group(1))
                if self.chapter is None:
                    if n == 1:
                        self.chapter = 1
                        self.bible[self.book].setdefault(1, {})
                        self.verse = 0
                    else:
                        self.buffer.append(line)
                        continue
                if self.verse < n <= self.verse + 3:
                    self._flush()
                    self.verse = n
                    self.bible[self.book][self.chapter][n] = vm.group(2).strip()
                    continue
            if self.chapter is not None:
                self.buffer.append(line)
        # Anything left at the end of a page continues the current verse.
        self._flush()


def parse_pdf(path: str | Path, books: range | None = None) -> dict[int, dict[int, dict[int, str]]]:
    """{book: {chapter: {verse: text}}} for the books wanted (all by default)."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parser = _Parser()
    for page in reader.pages:
        parser.page(page.extract_text() or "")
    bible = parser.bible
    if books is not None:
        bible = {b: v for b, v in bible.items() if b in books}
    return bible


def save(bible: dict, path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {str(b): {str(c): {str(v): t for v, t in sorted(vs.items())} for c, vs in sorted(chs.items())} for b, chs in sorted(bible.items())}
    path.write_text(json.dumps({"source": SOURCE, "books": out}, ensure_ascii=False, indent=0), encoding="utf-8")


_memory: dict | None = None


def _from_file() -> dict:
    global _memory
    if _memory is None:
        try:
            _memory = json.loads(DATA_FILE.read_text(encoding="utf-8")).get("books", {})
        except Exception:
            _memory = {}
    return _memory


def chapter_verses(db, book: int, chapter: int) -> dict[str, str]:
    """Verses of one chapter from the database (``bible_chapters`` with
    lang ``chk_lm``), else from the bundled data file."""
    if db is not None:
        try:
            doc = db[COLLECTION].find_one({"lang": LANG, "book": book, "chapter": chapter}, {"verses": 1})
            if doc and doc.get("verses"):
                return doc["verses"]
        except Exception:
            pass
    return _from_file().get(str(book), {}).get(str(chapter), {})


def verse(db, book: int, chapter: int, number: int) -> str:
    return chapter_verses(db, book, chapter).get(str(number), "")


__all__ = ["BOOK_LABELS", "SOURCE", "LANG", "book_number", "parse_pdf", "save", "chapter_verses", "verse"]
