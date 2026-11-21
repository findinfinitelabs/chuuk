"""
Scripture Lookup API.

Every verse comes from the uploaded Bibles stored in ``bible_chapters`` (the
New World Translation in English for Genesis–Revelation and in Chuukese for
Matthew–Revelation, the Liebenzell Paipel for Chuukese Genesis–Malachi).
Nothing is fetched from the network and nothing is translated.

Routes
    GET /api/bible/books                     the 66 books: number, English and Chuukese name, chapter count
    GET /api/bible/chapter?book=43&chapter=3 one chapter in both languages, with the gloss maps
    GET /api/bible/lookup?q=John 3:16, 17    a citation as jw.org accepts it → the cited verses per chapter

Each verse with both languages carries ``links``: the Chuukese ↔ English word
pairs found through the dictionary (see src/core/word_links.py).
"""

from __future__ import annotations

import re
from typing import Callable

from flask import Blueprint, jsonify, request

from src.core import liebenzell_bible, nwt_bible
from src.core.scripture_refs import BOOKS, canonical_book, expand

# Chapters per book, as counted in the uploaded New World Translation.
CHAPTERS = [
    50, 40, 27, 36, 34, 24, 21, 4, 31, 24, 22, 25, 29, 36, 10, 13, 10, 42, 150, 31, 12, 8, 66, 52, 5, 48, 12, 14, 3, 9,
    1, 4, 7, 3, 3, 3, 2, 14, 4, 28, 16, 24, 21, 28, 16, 16, 13, 6, 6, 4, 4, 5, 3, 6, 4, 3, 1, 13, 5, 5, 3, 5, 1, 1, 1, 22,
]

# Chuukese book names: Genesis–Malachi as the Liebenzell Paipel titles them,
# Matthew–Revelation as the Chuukese New World Translation does.
CHK_NAMES = [
    "Keneses", "Ekistos", "Lifitikos", "Numperis", "Tuteronomi", "Josua", "Soukapwúng", "Rut", "1 Samuel", "2 Samuel",
    "1 King", "2 King", "1 Kronika", "2 Kronika", "Esra", "Nehemia", "Ester", "Hiop", "Kölfel", "Än Salomon Fos",
    "Än Salomon Afalafal", "Än Salomon Köl", "Aisea", "Jeremaia", "Kölün Kechü", "Isikiel", "Taniel", "Osea", "Sowel", "Amos",
    "Opataia", "Sona", "Mika", "Nahum", "Apakuk", "Sefanaia", "Akai", "Sekaraia", "Malakai",
    "Mattu", "Mark", "Luk", "Jon", "Féffér", "Rom", "1 Korint", "2 Korint", "Kalesia", "Efisus", "Filipai",
    "Kolose", "1 Tesalonika", "2 Tesalonika", "1 Timoty", "2 Timoty", "Taitos", "Filimon", "Ipru",
    "Jemes", "1 Piter", "2 Piter", "1 Jon", "2 Jon", "3 Jon", "Juta", "Pwáraatá",
]

MAX_VERSES = 200
_BOOK_CHAPTER = re.compile(r"^\s*([1-3]?\s?[^\d\s][^\d:]*?)\.?\s*(\d+)\s*$")
_BOOK_ONLY = re.compile(r"^\s*([1-3]?\s?[^\d\s][^\d:]*?)\.?\s*$")


def book_info(number: int) -> dict:
    return {"number": number, "name": BOOKS[number - 1], "chk_name": CHK_NAMES[number - 1], "chapters": CHAPTERS[number - 1]}


def parse_query(q: str) -> list[tuple[int, int, list[int] | None]]:
    """(book, chapter, verses or None for the whole chapter) for every passage
    of a citation: 'John 3:16, 17; 4:1' → two passages, 'Ps 23' → the chapter,
    'Jude' → chapter 1. Unknown books are skipped."""
    out: list[tuple[int, int, list[int] | None]] = []
    seen: dict[tuple[int, int], int] = {}
    last_book = None
    for part in re.split(r"\s*;\s*", (q or "").strip()):
        if not part:
            continue
        if ":" in part:
            # Verse citations; a bare "4:1" continues the previous book.
            text = part if re.match(r"^\s*[^\d\s]", part) or last_book is None else f"{BOOKS[last_book - 1]} {part}"
            for _label, query in expand(text):
                m = re.match(r"^(.+?) (\d+):(\d+)$", query)
                if not m or m.group(1) not in BOOKS:
                    continue
                book, chapter, verse = BOOKS.index(m.group(1)) + 1, int(m.group(2)), int(m.group(3))
                last_book = book
                key = (book, chapter)
                if key not in seen:
                    seen[key] = len(out)
                    out.append((book, chapter, []))
                verses = out[seen[key]][2]
                if verses is not None and verse not in verses:
                    verses.append(verse)
            continue
        m = _BOOK_CHAPTER.match(part)
        if m and canonical_book(m.group(1)):
            book = BOOKS.index(canonical_book(m.group(1))) + 1
            last_book = book
            out.append((book, int(m.group(2)), None))
            continue
        if part.strip().isdigit() and last_book:
            out.append((last_book, int(part), None))
            continue
        m = _BOOK_ONLY.match(part)
        if m and canonical_book(m.group(1)):
            book = BOOKS.index(canonical_book(m.group(1))) + 1
            last_book = book
            out.append((book, 1, None))
    return out


def create_blueprint(get_db: Callable, login_required: Callable, analyzer: Callable | None = None) -> Blueprint:
    bp = Blueprint("bible", __name__)

    def db():
        d = get_db()
        return getattr(d, "db", None) if d is not None else None

    def maps_for(chk_text: str) -> dict:
        if not analyzer or not chk_text:
            return {"dictionary": {}, "similar": {}, "phrases": {}}
        try:
            m = analyzer(chk_text)
            return {"dictionary": m.get("dictionary", {}), "similar": m.get("similar", {}), "phrases": m.get("phrases", {})}
        except Exception:
            return {"dictionary": {}, "similar": {}, "phrases": {}}

    def passage(book: int, chapter: int, only: list[int] | None) -> dict | None:
        if not 1 <= book <= 66 or not 1 <= chapter <= CHAPTERS[book - 1]:
            return None
        d = db()
        en = nwt_bible.chapter_verses(d, "en", book, chapter)
        if book >= 40:
            chk, source_chk = nwt_bible.chapter_verses(d, "chk", book, chapter), "nwt"
        else:
            chk, source_chk = liebenzell_bible.chapter_verses(d, book, chapter), "liebenzell"
        numbers = sorted({int(n) for n in list(en) + list(chk) if str(n).isdigit()})
        wanted = sorted(set(only)) if only else numbers
        rows = [{"n": n, "en": en.get(str(n), ""), "chk": chk.get(str(n), "")} for n in wanted if n in numbers or only][:MAX_VERSES]
        missing = [r["n"] for r in rows if not (r["en"] or r["chk"])]
        rows = [r for r in rows if r["en"] or r["chk"]]
        maps = maps_for(" ".join(r["chk"] for r in rows if r["chk"]))
        # Word links: which English word each Chuukese word corresponds to (word_links).
        try:
            from src.core.word_links import linker_for

            linker = linker_for(get_db())
            for r in rows:
                if r["chk"] and r["en"]:
                    r["links"] = linker.link(r["chk"], r["en"], maps["dictionary"])
        except Exception:
            pass
        info = book_info(book)
        label = f"{info['name']} {chapter}" + (f":{_spec(wanted)}" if only else "")
        return {
            **info, "chapter": chapter, "label": label, "whole": only is None,
            "verses": rows, "highlight": sorted(set(only)) if only else [],
            "missing": missing, "source_chk": source_chk,
            "source_en": nwt_bible.SOURCE_EN,
            "source_chk_label": nwt_bible.SOURCE_CHK if source_chk == "nwt" else liebenzell_bible.SOURCE,
            "prev": {"book": book, "chapter": chapter - 1} if chapter > 1 else ({"book": book - 1, "chapter": CHAPTERS[book - 2]} if book > 1 else None),
            "next": {"book": book, "chapter": chapter + 1} if chapter < CHAPTERS[book - 1] else ({"book": book + 1, "chapter": 1} if book < 66 else None),
            "maps": maps,
        }

    @bp.route("/api/bible/books")
    @login_required
    def api_books():
        return jsonify([book_info(n) for n in range(1, 67)])

    @bp.route("/api/bible/chapter")
    @login_required
    def api_chapter():
        try:
            book, chapter = int(request.args.get("book", 0)), int(request.args.get("chapter", 0))
        except ValueError:
            return jsonify({"error": "book and chapter must be numbers"}), 400
        p = passage(book, chapter, None)
        if p is None:
            return jsonify({"error": "No such chapter"}), 404
        highlight = [int(x) for x in re.findall(r"\d+", request.args.get("highlight", ""))]
        p["highlight"] = highlight
        return jsonify(p)

    @bp.route("/api/bible/lookup")
    @login_required
    def api_lookup():
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"error": "Type a citation, such as John 3:16"}), 400
        parsed = parse_query(q)
        if not parsed:
            return jsonify({"error": "Could not read this citation. Try a form like John 3:16, Ps 23 or 1 Pe 3:1, 2, 15.", "query": q}), 400
        passages = [p for p in (passage(b, c, v) for b, c, v in parsed[:8]) if p]
        if not passages:
            return jsonify({"error": "No such chapter in the Bible.", "query": q}), 404
        return jsonify({"query": q, "passages": passages})

    return bp


def _spec(verses: list[int]) -> str:
    """[1, 2, 3, 7] → '1-3, 7'."""
    parts: list[str] = []
    i = 0
    while i < len(verses):
        j = i
        while j + 1 < len(verses) and verses[j + 1] == verses[j] + 1:
            j += 1
        parts.append(str(verses[i]) if j == i else f"{verses[i]}-{verses[j]}")
        i = j + 1
    return ", ".join(parts)


__all__ = ["create_blueprint", "parse_query", "book_info", "CHAPTERS", "CHK_NAMES"]
