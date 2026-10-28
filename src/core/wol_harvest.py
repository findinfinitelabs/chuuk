"""
Harvest Chuukese/English sentence pairs from wol.jw.org publications.

A Chuukese article and its English edition share a document id, and their
paragraphs share ``data-pid`` values. So a whole publication year can be
turned into aligned pairs by walking the Chuukese library index to the
articles, fetching each article in both languages, and pairing paragraphs by
id — then sentences within a paragraph by position when both sides split
into the same number of sentences.

This module is the logic: index parsing, pairing, record shaping. The
fetching lives in ``scripts/harvest_wol_pairs.py`` behind a polite,
rate-limited session, because every request lands on wol.jw.org.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from src.core.wol_search import WOL_BASE, _clean, _plain, _split_sentences

CHK_LIBRARY = "/chk/wol/library/r303/lp-te/meinisin-mi-peres"
# Library slugs of the publications we harvest, as they appear in the Chuukese index.
PUBLICATIONS = {
    "watchtower": {"slug": "ewe-leenien-mas", "code": "w"},
    "mwb": {"slug": "minen-káé-fán-iten-mwiich", "code": "mwb"},
}
# The study edition of the Watchtower sits one level below the year page.
WATCHTOWER_EDITIONS = {"study": "fán-iten-ewe-mwichefel", "public": "puk-fán-iten-aramas-meinisin"}

_DOC_HREF = re.compile(r"^/chk/wol/d/r303/lp-te/(\d+)")
# A scripture citation's chapter:verse part ("127:4", "131:1, 2"). Page and
# paragraph numbers differ between editions, so only these are compared.
_CHAPTER_VERSE = re.compile(r"\b(\d+):(\d+(?:\s*[-,]\s*\d+)*)")
_WORD = re.compile(r"[^\W_]+", re.UNICODE)

MAX_PARAGRAPH_WORDS = 70
MIN_WORDS = 3


def _links(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = unquote(a["href"].split("?")[0])
        text = _clean(a.get_text(" ", strip=True))
        out.append((href, text))
    return out


def child_links(html: str, parent_path: str) -> list[tuple[str, str]]:
    """Library links one level below `parent_path`, in page order, unique."""
    parent = unquote(parent_path).rstrip("/")
    seen = set()
    out = []
    for href, text in _links(html):
        if not href.startswith(parent + "/"):
            continue
        rest = href[len(parent) + 1 :]
        if "/" in rest or not rest or href in seen:
            continue
        seen.add(href)
        out.append((href, text))
    return out


def doc_links(html: str) -> list[tuple[str, str]]:
    """Article links on an issue page as (doc_id, title), unique, in order."""
    seen = set()
    out = []
    for href, text in _links(html):
        m = _DOC_HREF.match(href)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        out.append((m.group(1), text))
    return out


def year_link(index_html: str, publication: str, year: int) -> str | None:
    """The year page of a publication in its library index. Slugs vary
    ("...-mwich-2025" vs "...-mwiich-2026"), so match on the year suffix."""
    slug = PUBLICATIONS[publication]["slug"]
    for href, _text in child_links(index_html, f"{CHK_LIBRARY}/{slug}"):
        if href.endswith(f"-{year}"):
            return href
    return None


def doc_url(doc_id: str, lang: str) -> str:
    if lang == "en":
        return f"{WOL_BASE}/en/wol/d/r1/lp-e/{doc_id}"
    return f"{WOL_BASE}/chk/wol/d/r303/lp-te/{doc_id}"


# ---------------------------------------------------------------------------
# Documents and pairing
# ---------------------------------------------------------------------------


def parse_document(html: str) -> dict:
    """{title, citation, paragraphs: [(pid, text)]} from an article page."""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup
    title_el = soup.select_one("li.resultsNavigationSelected .navContent") or soup.find("h1")
    location = soup.select_one("li.documentLocation")
    seen = set()
    paragraphs = []
    for p in article.select("[data-pid]"):
        pid = p.get("data-pid")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        paragraphs.append((pid, _plain(p)))
    return {
        "title": _clean(title_el.get_text(" ", strip=True)) if title_el else None,
        "citation": _clean(location.get_text(" ", strip=True)) if location else None,
        "paragraphs": paragraphs,
    }


def _words(text: str) -> int:
    return len(_WORD.findall(text or ""))


def _norm(text: str) -> str:
    return re.sub(r"[^\w]+", " ", (text or "").lower()).strip()


def _citations(text: str) -> set[str]:
    out = set()
    for chapter, verses in _CHAPTER_VERSE.findall(text or ""):
        out.add(chapter + ":" + re.sub(r"\s+", "", verses))
    return out


def _worth_keeping(chk: str, eng: str) -> bool:
    """Skip headings and labels that are identical in both editions,
    fragments too short to teach anything, and lines whose scripture
    citations disagree — the editions sometimes pick different verses for
    the same slot (a "spiritual gems" question, say), and then the two
    texts are not translations of each other."""
    if _words(chk) < MIN_WORDS or _words(eng) < MIN_WORDS:
        return False
    if _norm(chk) == _norm(eng):
        return False
    chk_refs, eng_refs = _citations(chk), _citations(eng)
    if chk_refs and eng_refs and chk_refs != eng_refs:
        return False
    return True


def pair_paragraph(pid: str, chk_text: str, eng_text: str) -> list[dict]:
    """Pairs from one paragraph present in both editions.

    Same sentence count on both sides → sentences paired by position, with a
    length-ratio check on each (a Chuukese sentence runs at most about 2.5×
    its English and rarely under a third). Different counts → the paragraph
    as a whole, when it is short enough to be a training example.
    """
    chk_sents = _split_sentences(chk_text)
    eng_sents = _split_sentences(eng_text)
    out = []
    if chk_sents and len(chk_sents) == len(eng_sents):
        for i, (c, e) in enumerate(zip(chk_sents, eng_sents)):
            if not _worth_keeping(c, e):
                continue
            ratio = len(e) / max(len(c), 1)
            if len(c) > 30 and (ratio > 2.5 or ratio < 0.33):
                continue
            out.append(
                {
                    "pid": pid,
                    "index": i,
                    "chuukese": c,
                    "english": e,
                    "type": "sentence",
                    # One sentence per paragraph is an exact pairing; several
                    # paired by position are almost always right but not certain.
                    "confidence_score": 95 if len(chk_sents) == 1 else 90,
                    "alignment": "exact" if len(chk_sents) == 1 else "positional",
                }
            )
        return out

    if _worth_keeping(chk_text, eng_text) and _words(chk_text) <= MAX_PARAGRAPH_WORDS and _words(eng_text) <= MAX_PARAGRAPH_WORDS:
        ratio = len(eng_text) / max(len(chk_text), 1)
        if 0.33 <= ratio <= 2.5:
            out.append(
                {
                    "pid": pid,
                    "index": 0,
                    "chuukese": chk_text,
                    "english": eng_text,
                    "type": "paragraph",
                    "confidence_score": 85,
                    "alignment": "paragraph",
                }
            )
    return out


def pair_documents(doc_id: str, chk: dict, eng: dict) -> list[dict]:
    """Every pair from a document in both editions."""
    eng_by_pid = dict(eng["paragraphs"])
    pairs = []
    for pid, chk_text in chk["paragraphs"]:
        eng_text = eng_by_pid.get(pid)
        if not eng_text:
            continue
        for p in pair_paragraph(pid, chk_text, eng_text):
            p["doc_id"] = doc_id
            pairs.append(p)
    return pairs


def pair_record(pair: dict, publication: str, year: int, chk_doc: dict, eng_doc: dict, now: datetime | None = None) -> dict:
    """The phrases-collection document for a pair, in the shape the
    Translation Game and Sentence Analysis use for sentence pairs, so the
    training-pair collector reads it unchanged."""
    now = now or datetime.now(timezone.utc)
    return {
        "_id": f"wol_{pair['doc_id']}_{pair['pid']}_{pair['index']}",
        "chuukese_sentence": pair["chuukese"],
        "chuukese_word": pair["chuukese"],
        "english_translation": pair["english"],
        "type": pair["type"],
        "confidence": round(pair["confidence_score"] / 100, 2),
        "confidence_score": pair["confidence_score"],
        "grammar": "phrase",
        "search_direction": "chk_to_en",
        "definition": "",
        "source": "wol.jw.org",
        "source_type": "wol_harvest",
        "alignment": pair["alignment"],
        "publication": PUBLICATIONS[publication]["code"],
        "year": year,
        "doc_id": pair["doc_id"],
        "pid": pair["pid"],
        "citation": chk_doc.get("citation"),
        "citation_en": eng_doc.get("citation"),
        "title": chk_doc.get("title"),
        "title_en": eng_doc.get("title"),
        "link": doc_url(pair["doc_id"], "chk") + f"#p{pair['pid']}",
        "link_en": doc_url(pair["doc_id"], "en") + f"#p{pair['pid']}",
        "user_confirmed": False,
        "harvested": True,
        "date_modified": now,
    }
