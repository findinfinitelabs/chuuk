"""
Sentence extraction and cross-language pairing for the Translation Game.

A wol.jw.org article and its translation share paragraph ids (``data-pid``), so
the English and Chuukese editions can be lined up paragraph by paragraph. This
module turns each edition into a flat list of sentences (every scripture
citation kept whole and attached to its sentence) and, from the shared
paragraph ids, works out which Chuukese sentences are the likely match for each
English one — the "clue" the game shows.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.core.wol_search import _plain as plain_text
from src.utils.scripture_parser import get_scripture_reference_pattern, split_sentences

_LEADING_BULLET = re.compile(r"^(?:[•●◦▪▫■□‣⁃∙*]+\s*)+")
# Study-article paragraph numbers: "8 Lón ei fansoun" → "Lón ei fansoun".
_PARAGRAPH_NUMBER = re.compile(r"^\d{1,3}\s+(?=[“‘\"(\[]?[A-ZÀ-Þ])")
_ENDNOTE_CLASS = re.compile(r"footnote|endnote|groupFootnote|boxContent")
_SCRIPTURE_LINK = re.compile(r"/bc/|/nwtsty/|/bible/")
_HAS_VERSE = re.compile(r"\d+:\d+")

MIN_PARAGRAPH_CHARS = 15
MIN_SENTENCE_CHARS = 20


def _is_endnote(element) -> bool:
    text = element.get_text(strip=True)
    if text.startswith("PWAL") or text.startswith("SEE ALSO"):
        return True
    return element.find_parent(class_=_ENDNOTE_CLASS) is not None


def _endnote_refs(element) -> list[str]:
    """Scripture references linked from an endnote, each as its own entry."""
    refs = []
    for link in element.find_all("a", href=True):
        text = link.get_text(strip=True)
        if _SCRIPTURE_LINK.search(link.get("href", "")) and _HAS_VERSE.search(text) and len(text) > 1:
            refs.append(text)
    return refs


def _paragraph_elements(article):
    """WOL paragraphs carry data-pid (shared across language editions). Other
    pages fall back to <p>/<li> elements that do not wrap further paragraphs."""
    with_pid = article.select("[data-pid]")
    if with_pid:
        return with_pid, True
    return [el for el in article.find_all(["p", "li"]) if not el.find("p")], False


def clean_paragraph(text: str) -> str:
    text = _LEADING_BULLET.sub("", text).strip()
    # Drop a study-paragraph number, but not the ordinal of "2 Piter 1:21".
    if not re.match(get_scripture_reference_pattern(), text):
        text = _PARAGRAPH_NUMBER.sub("", text)
    return text.strip()


def _title(soup) -> str:
    """WOL document pages have no <h1>: the article title is the selected entry in
    the publication navigation, and the <title> is "Article — Watchtower ONLINE LIBRARY"."""
    for selector in ("h1", "li.resultsNavigationSelected .navContent"):
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            return el.get_text(" ", strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return re.split(r"\s+[—|-]\s+", soup.title.get_text(" ", strip=True))[0].strip()
    return "Untitled"


def parse_article(html: str) -> dict:
    """Parse one article into ``{"title", "has_pids", "sentences"}``.

    Each sentence is ``{id, text, paragraph_index, pid, sentence_index,
    sentence_count, span}`` where ``span`` is the sentence's [start, end]
    position within its paragraph as fractions of the paragraph's length.
    Endnote scripture references become ``is_scripture_ref`` entries.
    """
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup.find("div", class_="bodyTxt")
    title = _title(soup)
    if not article:
        return {"title": title, "has_pids": False, "sentences": []}

    elements, has_pids = _paragraph_elements(article)
    sentences: list[dict] = []
    seen_pids: set[str] = set()

    for idx, para in enumerate(elements):
        pid = para.get("data-pid") if has_pids else None
        if pid is not None:
            if pid in seen_pids:  # nested elements sharing a pid
                continue
            seen_pids.add(pid)

        if _is_endnote(para):
            for ref in _endnote_refs(para):
                sentences.append(
                    {
                        "id": len(sentences) + 1,
                        "text": f"📖 {ref}",
                        "paragraph_index": idx,
                        "pid": pid,
                        "sentence_index": 0,
                        "sentence_count": 1,
                        "span": [0.0, 1.0],
                        "is_scripture_ref": True,
                    }
                )
            continue

        text = clean_paragraph(plain_text(para))
        if len(text) < MIN_PARAGRAPH_CHARS:
            continue

        parts = [s for s in split_sentences(text) if len(s) >= MIN_SENTENCE_CHARS]
        total = sum(len(p) for p in parts) or 1
        offset = 0
        for n, part in enumerate(parts):
            start, offset = offset, offset + len(part)
            sentences.append(
                {
                    "id": len(sentences) + 1,
                    "text": part,
                    "paragraph_index": idx,
                    "pid": pid,
                    "sentence_index": n,
                    "sentence_count": len(parts),
                    "span": [round(start / total, 3), round(offset / total, 3)],
                }
            )

    return {"title": title, "has_pids": has_pids, "sentences": sentences}


def _overlap(a: list[float], b: list[float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def align_hints(english: list[dict], chuukese: list[dict], min_overlap: float = 0.3) -> dict[int, dict]:
    """For each English sentence, the Chuukese sentences in the same paragraph
    and, among them, the likely translation(s).

    Returns ``{english_id: {"paragraph": [chk ids], "likely": [chk ids]}}``.
    Paragraphs pair by shared ``pid``; when neither edition has pids they pair
    by position, but only if both have the same number of paragraphs.
    """

    def key_for(sentences, use_index):
        return (lambda s: f"idx:{s['paragraph_index']}") if use_index else (lambda s: s.get("pid"))

    en_has_pids = any(s.get("pid") for s in english)
    chk_has_pids = any(s.get("pid") for s in chuukese)
    if en_has_pids and chk_has_pids:
        use_index = False
    else:
        en_paras = {s["paragraph_index"] for s in english}
        chk_paras = {s["paragraph_index"] for s in chuukese}
        if len(en_paras) != len(chk_paras):
            return {}
        use_index = True
    en_key, chk_key = key_for(english, use_index), key_for(chuukese, use_index)

    by_para: dict[str, list[dict]] = {}
    for s in chuukese:
        k = chk_key(s)
        if k is not None:
            by_para.setdefault(k, []).append(s)

    hints: dict[int, dict] = {}
    for e in english:
        k = en_key(e)
        candidates = by_para.get(k) if k is not None else None
        if not candidates:
            continue
        if e.get("is_scripture_ref"):
            likely = [c for c in candidates if c.get("is_scripture_ref")]
        elif len(candidates) == e["sentence_count"] and e["sentence_index"] < len(candidates):
            # Same sentence count on both sides: the n-th sentence is the n-th.
            likely = [candidates[e["sentence_index"]]]
        else:
            # Otherwise the sentence(s) occupying the same stretch of the paragraph.
            width = max(e["span"][1] - e["span"][0], 1e-6)
            scored = [(c, _overlap(e["span"], c["span"]) / width) for c in candidates]
            likely = [c for c, score in scored if score >= min_overlap]
            if not likely:
                likely = [max(scored, key=lambda cs: cs[1])[0]]
        hints[e["id"]] = {
            "paragraph": [c["id"] for c in candidates],
            "likely": [c["id"] for c in likely],
        }
    return hints


__all__ = ["parse_article", "align_hints", "clean_paragraph"]
