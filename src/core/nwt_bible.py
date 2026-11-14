"""
The New World Translation of the Holy Scriptures from the files Chris
uploaded, so that the Talk Builder never has to fetch a verse from
wol.jw.org and never translates the Bible:

  * English, Genesis–Revelation: ``nwt_E.pdf`` (two text columns with a
    column of marginal references between them and footnotes at the foot).
  * Chuukese, Matthew–Revelation: ``nwt_TE.epub`` (read with the existing
    ``NWTEpubParser``).

Genesis–Malachi in Chuukese keep coming from the Liebenzell Paipel
(``liebenzell_bible``).

Both are parsed once into ``data/bible/nwt_en.json`` / ``nwt_chk_gs.json``
and imported into the Cosmos ``bible_chapters`` collection (lang ``en`` /
``chk``), which the app reads; the JSON files are the fallback.

PDF geometry the parser relies on (pdftotext -bbox-layout, points):

    header line           y < 32, "GENESIS 1:20–2:5" or "1601 HEBREWS Contents –2:3"
    left text column      x < 138       right text column   x >= 174
    marginal references   138 <= x < 174, small type (height < 5.5)
    verse text            height ≈ 6.2  verse number  height ≈ 9.1
    chapter numeral       height ≈ 20   (a drop cap; verse 1 is unnumbered)
    footnotes             height 5.9 / 6.9, below a rule near the foot
    footnote markers      height 8.4 (control characters), cross-ref letters 3.8
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "bible"
EN_FILE = DATA_DIR / "nwt_en.json"
CHK_FILE = DATA_DIR / "nwt_chk_gs.json"
COLLECTION = "bible_chapters"
SOURCE_EN = "New World Translation (English, nwt_E.pdf)"
SOURCE_CHK = "New World Translation (Chuukese, nwt_TE.epub)"

BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther",
    "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
    "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah",
    "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians", "Galatians",
    "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy",
    "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation",
]
_HEADER_BOOK = {b.upper(): i + 1 for i, b in enumerate(BOOKS)}
_HEADER_BOOK["PSALM"] = 19
_HEADER_BOOK["LAMENTATIONS"] = 25
_HEADER_BOOK["SONG OF SOLOMON"] = 22

_WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')
_LEFT_MAX, _RIGHT_MIN = 138.0, 174.0
_FOOT_SIZE = (5.5, 6.6)  # verse text height; footnotes are 5.9 (text) and 6.9 (refs) — see _is_text


def _page_words(pdf: str, page: int) -> list[tuple[float, float, float, float, str]]:
    out = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), "-bbox-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
    return [(float(a), float(b), float(c), float(d), t) for a, b, c, d, t in _WORD.findall(out)]


def _clean(token: str) -> str:
    # footnote markers come through as control characters; ligatures as single glyphs
    token = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", token)
    return token.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff").replace("ﬃ", "ffi").replace("ﬄ", "ffl")


_HEADER_Y = 28.0  # the running head sits at y≈23; a chapter numeral can start at y≈31


_TITLE_BOOK = {re.sub(r"\s+", "", b.upper()): i + 1 for i, b in enumerate(BOOKS)}


def _header(words) -> tuple[int | None, int | None, str]:
    """(book the page starts in, book that begins on this page or None, header text).
    A page where a book ends and the next begins reads "AMOS 9:11–OBADIAH 3" or
    "NUMBERS 36:1 – DEUTERONOMY Contents"."""
    text = " ".join(t for x1, y1, x2, y2, t in sorted(words, key=lambda w: w[0]) if y1 < _HEADER_Y)
    found = []
    for half in re.split(r"\s*[–\-]\s*", text):
        # drop page numbers (2+ digits), chapter:verse refs and "Contents"; keep the "1" of "1 SAMUEL"
        keep = [t for t in half.split() if not (re.fullmatch(r"\d{2,}", t) or ":" in t or t == "Contents")]
        while keep and keep[-1].isdigit():   # "OBADIAH 4" (a single-chapter book's verse number)
            keep.pop()
        name = " ".join(keep).upper().strip()
        parts = name.split(" ")
        for cand in (name, " ".join(parts[-2:]), parts[-1] if parts else ""):
            if cand in _HEADER_BOOK:
                found.append(_HEADER_BOOK[cand])
                break
    if not found:
        return None, None, text
    return found[0], (found[1] if len(found) > 1 and found[1] != found[0] else None), text


def parse_pdf(pdf: str, first: int = 1, last: int | None = None, log=print) -> dict[int, dict[int, dict[int, str]]]:
    """{book: {chapter: {verse: text}}} for the English NWT PDF."""
    if last is None:
        info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
        last = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    bible: dict[int, dict[int, dict[int, str]]] = {}
    book = chapter = verse = None
    buf: list[str] = []

    def flush():
        if book and chapter and verse and buf:
            text = " ".join(buf)
            text = re.sub(r"(\w)- (\w)", r"\1\2", text)      # line-break hyphenation
            text = re.sub(r"\s+([,.;:!?’”)])", r"\1", text)
            text = re.sub(r"\s+", " ", text).strip()
            d = bible.setdefault(book, {}).setdefault(chapter, {})
            d[verse] = (d.get(verse, "") + " " + text).strip()
        buf.clear()

    for page in range(first, last + 1):
        words = _page_words(pdf, page)
        hbook, next_book, htext = _header(words)
        # Book titles (≥ 22 high) and centred division lines such as "BOOK FOUR" or
        # "TO THE" (9.2 high, not digits) span both columns.
        page_titles: dict[int, list[str]] = {}
        dividers: dict[int, list[str]] = {}
        for x1, y1, x2, y2, t in words:
            h = y2 - y1
            if h >= 22:
                page_titles.setdefault(round(y1 / 6), []).append(t)
            elif 8.9 <= h <= 9.4 and t.strip().isalpha() and y1 >= _HEADER_Y and 100 <= x1 <= 180:
                dividers.setdefault(round(y1 / 6), []).append(t)
        opening_title = None
        if book == 66 and hbook is None and chapter == 22:
            break                                         # the appendix follows Revelation
        if hbook is None:
            # a book's opening page carries its title instead of a running head;
            # books come in canonical order, so the title only confirms the next one
            tok = "".join(page_titles[min(page_titles)]).upper() if page_titles else ""
            if not tok:
                continue
            opened = (book + 1) if book else _TITLE_BOOK.get(tok)
            if opened is None:
                continue
            if _TITLE_BOOK.get(tok) not in (None, opened):
                log(f"  page {page}: title {tok!r} where {BOOKS[opened - 1]} was expected")
            flush()
            book, chapter, verse, next_book = opened, 1, 1, None
            hbook = book
            opening_title = min(page_titles)
        elif hbook != book:
            flush()
            book, chapter, verse = hbook, None, None
        if chapter is None:
            # the page header names the first verse on the page ("GENESIS 1:20–2:5";
            # a single-chapter book reads "PHILEMON 21")
            m = re.search(r"(\d+):(\d+)", htext)
            if m:
                chapter, verse = int(m.group(1)), int(m.group(2))
            else:
                m = re.search(r"[A-Z]\s+(\d+)\b", htext)
                chapter, verse = 1, (int(m.group(1)) if m else 1)
        # footnotes (5.9 / 6.9 high) and superscriptions (5.1) fall out by height alone.
        # A book title (≥ 22 high) spans both columns: the columns restart below it.
        titles = {k: v for k, v in page_titles.items() if k * 6 >= _HEADER_Y and k != opening_title}
        title_ys = sorted(set(titles) | set(dividers))
        # a verse number can come out as separate digits ("4" "7" around a footnote mark)
        numbers = sorted((w for w in words if 8.9 <= w[3] - w[1] <= 9.4 and w[4].strip().isdigit()), key=lambda w: (round(w[1]), w[0]))
        merged, i = [], 0
        while i < len(numbers):
            x1, y1, x2, y2, t = numbers[i]
            while i + 1 < len(numbers) and abs(numbers[i + 1][1] - y1) < 2 and -1 <= numbers[i + 1][0] - x2 < 6:
                t, x2 = t + numbers[i + 1][4].strip(), numbers[i + 1][2]
                i += 1
            merged.append((x1, y1, x2, y2, t))
            i += 1
        items = []  # (band, column, y, x, kind, token)
        for x1, y1, x2, y2, t in [w for w in words if not (8.9 <= w[3] - w[1] <= 9.4 and w[4].strip().isdigit())] + merged:
            if y1 < _HEADER_Y or _LEFT_MAX <= x1 < _RIGHT_MIN:
                continue
            h = y2 - y1
            col = 0 if x1 < _LEFT_MAX else 1
            band = sum(1 for ty in title_ys if ty * 6 < y1 - 3)
            if 6.15 <= h <= 6.3:            # verse text is 6.22; a book's contents outline is 6.09
                items.append((band, col, y1, x1, "w", _clean(t)))
            elif 8.9 <= h <= 9.4 and t.strip().isdigit():
                items.append((band, col, y1 + 2, x1, "v", t.strip()))       # verse numbers sit a little high
            elif h >= 18 and t.strip().isdigit():
                items.append((band, col, y1 + 0.5, x1 - 1000, "c", t.strip()))  # chapter numeral precedes its line
        for i, ty in enumerate(title_ys):
            if ty in titles:
                items.append((i + 1, -1, 0.0, 0.0, "t", "".join(titles[ty]).upper()))
        # reading order: band, column, line (y bucketed), x
        items.sort(key=lambda it: (it[0], it[1], round(it[2] / 4), it[3]))
        for band, col, y, x, kind, tok in items:
            if kind == "t":
                flush()
                new_book = next_book or (book + 1 if book == hbook else None)
                if new_book is None:
                    log(f"  page {page}: title {tok!r} not recognised; staying in {BOOKS[book - 1]}")
                else:
                    if _TITLE_BOOK.get(tok) not in (None, new_book):
                        log(f"  page {page}: title {tok!r} where {BOOKS[new_book - 1]} was expected")
                    book, next_book = new_book, None
                chapter, verse = 1, 1
            elif kind == "c":
                flush()
                if tok == "1" and next_book:
                    book, next_book = next_book, None
                chapter, verse = int(tok), 1
            elif kind == "v":
                flush()
                verse = int(tok)
            elif tok:
                buf.append(tok)
        if page % 100 == 0:
            log(f"  page {page}: {BOOKS[book - 1]} {chapter}")
    flush()
    return bible


_VERSE_MARK = re.compile(r'<span id="chapter(\d+)_verse(\d+)"></span>')


def parse_epub(epub: str, books=range(40, 67)) -> dict[int, dict[int, dict[int, str]]]:
    """Chuukese NWT from the EPUB. Every chapter file starts with a
    navigation line linking ``bibleversenav<book>_<chapter>.xhtml`` and
    carries empty ``<span id="chapterN_verseM">`` markers; the text between
    two markers is the verse, minus verse/chapter numerals, footnote
    asterisks and the footnotes block at the end."""
    import zipfile

    z = zipfile.ZipFile(epub)
    bible: dict[int, dict[int, dict[int, str]]] = {}
    for name in z.namelist():
        if not name.endswith(".xhtml"):
            continue
        html = z.read(name).decode("utf-8", "ignore")
        nav = re.search(r'<p class="w_navigation[^"]*">(.*?)</p>', html, re.S)
        m = re.search(r"bibleversenav(\d+)_(\d+)", nav.group(1)) if nav else None
        if not m or "_verse" not in html:
            continue
        book, chapter = int(m.group(1)), int(m.group(2))
        if book not in books:
            continue
        html = html.split('<div class="groupFootnote"', 1)[0]
        html = html[nav.end():]
        html = re.sub(r"<strong>.*?</strong>", " ", html, flags=re.S)            # verse and chapter numerals
        html = re.sub(r'<a epub:type="noteref"[^>]*>\*</a>', "", html)
        html = _VERSE_MARK.sub(lambda mm: f"\x00{mm.group(2)}\x00", html)
        text = re.sub(r"<[^>]+>", " ", html)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        verses: dict[int, str] = {}
        parts = text.split("\x00")
        for i in range(1, len(parts) - 1, 2):
            number = int(parts[i])
            body = re.sub(r"\s+", " ", parts[i + 1]).strip()
            if body:
                verses[number] = (verses.get(number, "") + " " + body).strip()
        if verses:
            bible.setdefault(book, {})[chapter] = verses
    return bible


def save(bible: dict, path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {str(b): {str(c): {str(v): t for v, t in sorted(vs.items())} for c, vs in sorted(chs.items())} for b, chs in sorted(bible.items())}
    path.write_text(json.dumps({"source": source, "books": out}, ensure_ascii=False, indent=0), encoding="utf-8")


_memory: dict[str, dict] = {}


def _from_file(lang: str) -> dict:
    if lang not in _memory:
        path = EN_FILE if lang == "en" else CHK_FILE
        try:
            _memory[lang] = json.loads(path.read_text(encoding="utf-8")).get("books", {})
        except Exception:
            _memory[lang] = {}
    return _memory[lang]


def chapter_verses(db, lang: str, book: int, chapter: int) -> dict[str, str]:
    """Verses of one chapter: the database first (``bible_chapters`` with lang
    ``en`` or ``chk``), else the bundled JSON. Never the network."""
    if db is not None:
        try:
            doc = db[COLLECTION].find_one({"lang": lang, "book": book, "chapter": chapter}, {"verses": 1})
            if doc and doc.get("verses"):
                return doc["verses"]
        except Exception:
            pass
    return _from_file(lang).get(str(book), {}).get(str(chapter), {})


def verse(db, lang: str, book: int, chapter: int, number: int) -> str:
    return chapter_verses(db, lang, book, chapter).get(str(number), "")


__all__ = ["BOOKS", "COLLECTION", "parse_pdf", "parse_epub", "save", "chapter_verses", "verse", "EN_FILE", "CHK_FILE", "SOURCE_EN", "SOURCE_CHK"]
