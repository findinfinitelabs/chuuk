"""
Bible verses from wol.jw.org, cached per chapter.

The New World Translation on WOL is read one chapter at a time
(``/chk/wol/b/r303/lp-te/nwt/{book}/{chapter}``, ``/en/wol/b/r1/lp-e/nwt/…``);
every verse is a ``span.v`` whose id is ``v{book}-{chapter}-{verse}-{part}``.
A chapter is fetched once, politely, and kept in the ``bible_chapters``
collection, so a talk that cites ten verses costs at most a few requests
the first time and none afterwards.

The Chuukese edition on WOL holds the Christian Greek Scriptures; a Hebrew
Scriptures chapter comes back empty, and the caller falls back to whatever
else it has (the local EPUB when present).
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from src.core.wol_search import WOL_BASE, _plain

_URL = {
    "chk": WOL_BASE + "/chk/wol/b/r303/lp-te/nwt/{book}/{chapter}",
    "en": WOL_BASE + "/en/wol/b/r1/lp-e/nwt/{book}/{chapter}",
}
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_VERSE_ID = re.compile(r"^v(\d+)-(\d+)-(\d+)-(\d+)$")
_MIN_INTERVAL = 2.5
_lock = threading.Lock()
_last = 0.0
_memory: dict[tuple, dict] = {}
COLLECTION = "bible_chapters"


def parse_chapter(html: str) -> dict[str, str]:
    """{verse number: text} for one chapter page; verse numbers stripped."""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup
    out: dict[str, list[str]] = {}
    for span in article.select("span.v[id]"):
        m = _VERSE_ID.match(span["id"])
        if not m:
            continue
        text = _plain(span)
        if m.group(4) == "1":
            text = re.sub(rf"^\s*{m.group(3)}\s+", "", text)
        out.setdefault(m.group(3), []).append(text)
    return {v: " ".join(t for t in parts if t).strip() for v, parts in out.items()}


def _fetch(lang: str, book: int, chapter: int, timeout: int = 30) -> dict[str, str] | None:
    global _last
    with _lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
    try:
        r = requests.get(_URL[lang].format(book=book, chapter=chapter), headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    return parse_chapter(r.text)


def chapter_verses(db, lang: str, book: int, chapter: int) -> dict[str, str]:
    """Verses of one chapter, from memory, then the database, then WOL."""
    key = (lang, book, chapter)
    if key in _memory:
        return _memory[key]
    col = db[COLLECTION] if db is not None else None
    if col is not None:
        try:
            doc = col.find_one({"lang": lang, "book": book, "chapter": chapter}, {"verses": 1})
            if doc and doc.get("verses"):
                _memory[key] = doc["verses"]
                return doc["verses"]
        except Exception:
            pass
    verses = _fetch(lang, book, chapter) or {}
    if verses:
        _memory[key] = verses
        if col is not None:
            try:
                col.update_one({"lang": lang, "book": book, "chapter": chapter}, {"$set": {"verses": verses, "fetched_at": datetime.now(timezone.utc)}}, upsert=True)
            except Exception:
                pass
    return verses


def verse(db, lang: str, book: int, chapter: int, number: int) -> str:
    return chapter_verses(db, lang, book, chapter).get(str(number), "")


__all__ = ["chapter_verses", "verse", "parse_chapter"]
