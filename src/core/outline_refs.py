"""
Resolve the publication references a talk outline cites — "w21.08 5 ¶9",
"lff lesson 16 points 4-5", "bt chap. 20 ¶13-20", "it-1 543" — to the
article on wol.jw.org, the cited paragraph(s) in English and, when the
publication exists in Chuukese, the same paragraph(s) in Chuukese; and mark
the key phrases of the outline point inside them so a learner sees which
paragraph to read and where the thought sits in the Chuukese.

How a reference is found
* Watchtower study edition (``wYY.MM page ¶n``): the Chuukese library index
  lists the study edition by year and issue; its articles share document ids
  with the English, and each English article states its page range, which
  picks the article for the cited page. Paragraph ``n`` is the paragraph
  whose text opens with that printed number.
* Love People (lmd), Enjoy Life Forever (lff), teaching brochure (th):
  the publication index lists lessons; a point is the paragraph opening
  with "n.".
* Chapter books (bt, cl, jy, kr, rr, lfb, lvs, bhs, ia): the publication
  index lists chapters; paragraphs by printed number.
* Insight (it-1/it-2) and anything else: a link to the publication, no text.

Fetching goes through one injected ``fetch(url) -> html | None`` so callers
decide on pacing and caching (the API uses a polite, Cosmos-backed fetcher).
"""

from __future__ import annotations

import re
from urllib.parse import quote, unquote

from bs4 import BeautifulSoup

from src.core import wol_harvest as wh
from src.core.conversation_sources import LMD
from src.core.sentence_align import align_sentences
from src.core.wol_search import WOL_BASE, _clean, _plain
from src.utils.scripture_parser import split_sentences

MONTHS = "january february march april may june july august september october november december".split()

_PARA_LIST = r"(\d+(?:\s*[-–,]\s*\d+)*)"
CITATION_RE = re.compile(
    r"(?P<w>\bw(?P<wy>\d{2})\.(?P<wm>\d{2})\s+(?P<wp>\d+)(?:-\d+)?\s*(?:¶\s*(?P<wpar>" + _PARA_LIST + r"))?)"
    r"|(?P<wo>\b(?P<wopub>wp|w|g|km)(?P<woy>\d{2})?\s+(?P<wom>\d{1,2})/(?P<wod>\d{1,2})\s+(?:pp?\.\s*)?(?P<wop>\d+)(?:-\d+)?\s*(?:(?:¶|par\.?|pars\.?)\s*(?P<wopar>" + _PARA_LIST + r"))?)"
    r"|(?P<lesson>\b(?P<lpub>lff|lmd|th)\s+(?:lesson|lesen|study|káé)\s+(?P<ln>\d+)(?:\s+(?:points?|nampa|point)\s+(?P<lpts>" + _PARA_LIST + r"))?)"
    r"|(?P<chap>\b(?P<cpub>bt|cl|jy|kr|rr|lfb|lvs|bhs|ia|od|cf|jr|lr|wp|sjj)\s+(?:chap\.|chapter|sópwun)\s*(?P<cn>\d+)(?:\s*¶\s*(?P<cpar>" + _PARA_LIST + r"))?)"
    r"|(?P<it>\bit-(?P<itv>[12])\s+(?P<itp>\d+)(?:-\d+)?)",
    re.I,
)
_STOP = set(
    "the and that with this from they them their have will your what when which there were been about into also than then "
    "more most some such only over very just like make made does doing done being because before after while where those these "
    "should would could other each many much every both between through during without within upon toward again still here "
    "jehovah god people bible verse read paragraph consider discuss question answer point points show explain help need way".split()
)


def numbers(spec: str | None) -> list[int]:
    """'13-20' → [13..20]; '4, 5' → [4, 5]."""
    out: list[int] = []
    for piece in re.split(r"\s*,\s*", (spec or "").strip()):
        m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", piece)
        if m and int(m.group(2)) >= int(m.group(1)) and int(m.group(2)) - int(m.group(1)) <= 30:
            out.extend(range(int(m.group(1)), int(m.group(2)) + 1))
        elif piece.strip().isdigit():
            out.append(int(piece))
    return out


def find_references(text: str) -> list[dict]:
    """Citations in an outline line, in order: [{raw, kind, …}]."""
    out = []
    for m in CITATION_RE.finditer(text or ""):
        if m.group("w"):
            out.append({"raw": m.group("w").strip(), "kind": "w", "pub": "w", "year": 2000 + int(m.group("wy")), "month": int(m.group("wm")), "day": None, "page": int(m.group("wp")), "paragraphs": numbers(m.group("wpar"))})
        elif m.group("wo"):
            pub = m.group("wopub").lower()
            if m.group("woy"):
                # "w12 11/1 23": year on the symbol, then month/day of the issue.
                yy = int(m.group("woy"))
                year, month, day = (2000 if yy < 50 else 1900) + yy, int(m.group("wom")), int(m.group("wod"))
            else:
                # "g 11/12 8", "km 5/09 3": no year on the symbol, so month/year.
                yy = int(m.group("wod"))
                year, month, day = (2000 if yy < 50 else 1900) + yy, int(m.group("wom")), None
            out.append({"raw": m.group("wo").strip(), "kind": "w", "pub": pub, "year": year, "month": month, "day": day, "page": int(m.group("wop")), "paragraphs": numbers(m.group("wopar"))})
        elif m.group("lesson"):
            out.append({"raw": m.group("lesson").strip(), "kind": "lesson", "pub": m.group("lpub").lower(), "lesson": int(m.group("ln")), "paragraphs": numbers(m.group("lpts"))})
        elif m.group("chap"):
            out.append({"raw": m.group("chap").strip(), "kind": "chapter", "pub": m.group("cpub").lower(), "chapter": int(m.group("cn")), "paragraphs": numbers(m.group("cpar"))})
        elif m.group("it"):
            out.append({"raw": m.group("it").strip(), "kind": "it", "pub": f"it-{m.group('itv')}", "page": int(m.group("itp")), "paragraphs": []})
    return out


# ---------------------------------------------------------------------------
# Key phrases
# ---------------------------------------------------------------------------


def key_words(text: str) -> list[str]:
    """Content words of an outline point, lowercase, for matching."""
    words = re.findall(r"[^\W\d_]+", CITATION_RE.sub(" ", text or "").lower())
    seen, out = set(), []
    for w in words:
        if len(w) >= 4 and w not in _STOP and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def _stem(w: str) -> str:
    return w[:5] if len(w) > 5 else w


def mark_words(text: str, keys: list[str]) -> list[dict]:
    """[{text, hit}] tokens of `text`, a token hit when it shares a stem with a key word."""
    stems = {_stem(k) for k in keys}
    out = []
    for tok in re.findall(r"\S+|\s+", text or ""):
        core = re.sub(r"[^\w]", "", tok.lower())
        out.append({"text": tok, "hit": bool(core) and _stem(core) in stems})
    return out


def _sentence_scores(sentences: list[str], keys: list[str]) -> list[int]:
    stems = {_stem(k) for k in keys}
    return [len({_stem(w) for w in re.findall(r"[^\W\d_]+", s.lower())} & stems) for s in sentences]


def highlight_paragraph(en: str, chk: str | None, keys: list[str], glosses: dict[str, str] | None = None) -> dict:
    """English sentences with their hit words marked, and the Chuukese
    sentence(s) that translate the English sentence(s) carrying the key
    phrase (by content alignment), with Chuukese words whose dictionary gloss
    contains a key word marked too."""
    en_sents = split_sentences(en or "")
    scores = _sentence_scores(en_sents, keys)
    best = max(scores) if scores else 0
    en_rows = [{"text": s, "hit": best > 0 and sc == best, "words": mark_words(s, keys)} for s, sc in zip(en_sents, scores)]
    chk_rows = None
    if chk:
        chk_sents = split_sentences(chk)
        pairs = align_sentences(chk_sents, en_sents) if en_sents else [[] for _ in chk_sents]
        hit_en = {i for i, r in enumerate(en_rows) if r["hit"]}
        stems = {_stem(k) for k in keys}
        chk_rows = []
        for s, en_idx in zip(chk_sents, pairs):
            words = []
            for tok in re.findall(r"\S+|\s+", s):
                core = re.sub(r"[^\w]", "", tok.lower())
                gloss = (glosses or {}).get(core, "")
                hit = bool(core) and any(_stem(g) in stems for g in re.findall(r"[^\W\d_]+", gloss.lower()))
                words.append({"text": tok, "hit": hit})
            chk_rows.append({"text": s, "hit": bool(set(en_idx) & hit_en), "english_indices": en_idx, "words": words})
    return {"english": en_rows, "chuukese": chk_rows}


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

_PAGES_RE = re.compile(r"pp?\.\s*(\d+)(?:\s*[-–]\s*(\d+))?")
_PRINTED = re.compile(r"^\s*(\d{1,3})(?:[.)]|\s)")
_QUESTION = re.compile(r"^\s*\d{1,3}(?:\s*[-–,]\s*\d{1,3})*\.\s")


def doc_url(doc_id: str, lang: str) -> str:
    return wh.doc_url(doc_id, lang)


def pub_index_url(pub: str, lang: str) -> str:
    return f"{WOL_BASE}/chk/wol/publication/r303/lp-te/{pub}" if lang == "chk" else f"{WOL_BASE}/en/wol/publication/r1/lp-e/{pub}"


def parse_document(html: str) -> dict:
    """{title, citation, paragraphs: [(pid, text)]} of one WOL article."""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup
    h1 = soup.find("h1")
    location = soup.select_one("li.documentLocation")
    paragraphs, seen = [], set()
    for el in article.select("[data-pid]"):
        pid = el.get("data-pid")
        text = _plain(el)
        if pid and text and pid not in seen:
            seen.add(pid)
            num = el.select_one("span.parNum[data-pnum]")
            pnum = num.get("data-pnum") if num is not None else None
            if pnum is None:
                m = _PRINTED.match(text)
                pnum = m.group(1) if m and len(text) > 40 else None
            paragraphs.append((pid, text, int(pnum) if pnum and pnum.isdigit() else None))
    return {
        "title": _clean(h1.get_text(" ", strip=True)) if h1 else "",
        "citation": _clean(location.get_text(" ", strip=True)) if location else "",
        "paragraphs": paragraphs,
    }


def page_range(citation: str) -> tuple[int, int] | None:
    m = _PAGES_RE.search(citation or "")
    if not m:
        return None
    a = int(m.group(1))
    return a, int(m.group(2) or a)


def paragraphs_by_number(paragraphs: list[tuple], wanted: list[int]) -> list[tuple[int, str, str]]:
    """[(number, pid, text)] of the paragraphs carrying a wanted paragraph
    number (the article's own numbering, not study questions)."""
    out = []
    for pid, text, pnum in paragraphs:
        if pnum in wanted and not _QUESTION.match(text):
            out.append((pnum, pid, text))
    return out


class Resolver:
    def __init__(self, fetch, glosser=None):
        """fetch(url) -> html | None; glosser(text) -> {chuukese word: english gloss}."""
        self.fetch = fetch
        self.glosser = glosser

    # -- locating -----------------------------------------------------------

    _EN_LIBRARY = "/en/wol/library/r1/lp-e/all-publications"
    _EN_PUBS = {"w": "watchtower", "wp": "watchtower", "g": "awake", "km": "our-kingdom-ministry"}

    def _english_issue_doc_ids(self, pub: str, year: int, month: int, day: int | None) -> list[str]:
        """Articles of one issue through the English library index: publication →
        year → (edition) → issue, matched by the text of the links so slugs
        need not be known. For 2008–2015 Watchtowers the 15th is the study
        edition and the 1st the public one."""
        root = f"{self._EN_LIBRARY}/{self._EN_PUBS.get(pub, pub)}"
        index = self.fetch(WOL_BASE + root)
        if not index:
            return []
        year_href = next((h for h, _t in wh.child_links(index, root) if h.endswith(f"-{year}") or f"-{year}/" in h), None)
        if not year_href:
            return []
        page = self.fetch(WOL_BASE + quote(year_href))
        if not page:
            return []
        children = wh.child_links(page, year_href)
        wanted_edition = None
        if pub == "w" and day:
            wanted_edition = "study" if day >= 15 else "public"
        elif pub == "wp":
            wanted_edition = "public"
        elif pub == "w":
            wanted_edition = "study"
        editions = [(h, t) for h, t in children if re.search(r"study|public|simplified", t, re.I)]
        if editions:
            pick = next(((h, t) for h, t in editions if wanted_edition and wanted_edition in t.lower()), None) or editions[0]
            page = self.fetch(WOL_BASE + quote(pick[0]))
            if not page:
                return []
            children = wh.child_links(page, pick[0])
        month_name = MONTHS[month - 1]
        issue = None
        for h, t in children:
            text = t.strip().lower()
            if text.startswith(month_name) and (day is None or re.search(rf"\b{day}\b", text) or not re.search(r"\d", text)):
                issue = h
                break
        if issue is None:
            for h, t in children:
                if t.strip().lower().startswith(month_name[:3]):
                    issue = h
                    break
        if issue is None:
            return []
        html = self.fetch(WOL_BASE + quote(issue))
        return [doc_id for doc_id, _ in wh.doc_links(html)] if html else []

    def lookup_doc_id(self, citation: str) -> str | None:
        """wol.jw.org's own citation lookup ("w12 11/1 23" → the article's
        document id). The lookup page renders the cited document and links
        it, so the first document link is the answer; None when the page is
        unavailable or the citation was not understood."""
        html = self.fetch(f"{WOL_BASE}/en/wol/l/r1/lp-e?q={quote(citation)}")
        if not html:
            return None
        for a in BeautifulSoup(html, "html.parser").select("a[href*='/wol/d/r1/lp-e/']"):
            m = re.search(r"/wol/d/r1/lp-e/(\d+)", a.get("href") or "")
            if m:
                return m.group(1)
        return None

    def _watchtower_doc_ids(self, year: int, month: int) -> list[str]:
        index = self.fetch(WOL_BASE + f"{wh.CHK_LIBRARY}/{wh.PUBLICATIONS['watchtower']['slug']}")
        year_href = wh.year_link(index, "watchtower", year) if index else None
        if not year_href:
            return []
        edition_href = f"{year_href}/{wh.WATCHTOWER_EDITIONS['study']}"
        edition = self.fetch(WOL_BASE + quote(edition_href))
        if not edition:
            return []
        issues = wh.child_links(edition, edition_href)
        # Issues sit in calendar order; match by month name when present, else by position.
        chosen = None
        for href, text in issues:
            if text.strip().lower() in (MONTHS[month - 1], MONTHS[month - 1][:3]) or unquote(href).lower().endswith("/" + MONTHS[month - 1]):
                chosen = href
                break
        if chosen is None and len(issues) >= month:
            chosen = issues[month - 1][0]
        if chosen is None:
            return []
        issue = self.fetch(WOL_BASE + quote(chosen))
        return [doc_id for doc_id, _ in wh.doc_links(issue)] if issue else []

    def _lesson_doc_id(self, pub: str, lesson: int, lang: str) -> str | None:
        if pub == "lmd" and 1 <= lesson <= 12:
            return LMD["lessons"][lesson - 1]
        html = self.fetch(pub_index_url(pub, lang))
        if not html:
            return None
        pat = re.compile(rf"^\s*(?:lesson|lesen|study|káé)\s+{lesson}\b", re.I)
        for a in BeautifulSoup(html, "html.parser").select("a[href*='/wol/d/']"):
            if pat.match(a.get_text(" ", strip=True)):
                m = re.search(r"/wol/d/[^/]+/[^/]+/(\d+)", a["href"])
                if m:
                    return m.group(1)
        return None

    def _chapter_doc_id(self, pub: str, chapter: int, lang: str) -> str | None:
        html = self.fetch(pub_index_url(pub, lang))
        if not html:
            return None
        pat = re.compile(rf"^\s*(?:chapter|chap\.|sópwun)\s+{chapter}\b|^\s*{chapter}\s", re.I)
        for a in BeautifulSoup(html, "html.parser").select("a[href*='/wol/d/']"):
            if pat.match(a.get_text(" ", strip=True)):
                m = re.search(r"/wol/d/[^/]+/[^/]+/(\d+)", a["href"])
                if m:
                    return m.group(1)
        return None

    def _doc(self, doc_id: str, lang: str) -> dict | None:
        html = self.fetch(doc_url(doc_id, lang))
        if not html:
            return None
        doc = parse_document(html)
        return doc if doc["paragraphs"] else None

    # -- resolving ----------------------------------------------------------

    def resolve(self, ref: dict, context: str = "") -> dict:
        keys = key_words(context)
        out = {"ref": ref["raw"], "kind": ref["kind"], "key_words": keys, "title": {"en": "", "chk": ""}, "links": {"en": None, "chk": None, "search": f"{WOL_BASE}/en/wol/l/r1/lp-e?q={quote(ref['raw'])}"}, "chuukese_available": False, "paragraphs": [], "note": ""}
        en_doc = chk_doc = None
        doc_id = None
        wanted = ref.get("paragraphs") or []

        if ref["kind"] == "w":
            out["links"]["search"] = f"{WOL_BASE}/en/wol/l/r1/lp-e?q={quote(ref['raw'])}"
            pub, day = ref.get("pub", "w"), ref.get("day")
            # WOL's own lookup answers the citation directly; the library
            # indexes are the fallback when the lookup page is unavailable.
            doc_id = self.lookup_doc_id(ref["raw"])
            en_doc = self._doc(doc_id, "en") if doc_id else None
            if not en_doc:
                doc_id = None
                study = pub == "w" and (day is None or day >= 15)
                candidates = self._watchtower_doc_ids(ref["year"], ref["month"]) if study else []
                if not candidates:
                    candidates = self._english_issue_doc_ids(pub, ref["year"], ref["month"], day)
                # The issue cover spans every page, so take the narrowest range holding the page.
                best = None
                for cand in candidates:
                    d = self._doc(cand, "en")
                    rng = page_range(d["citation"]) if d else None
                    if rng and rng[0] <= ref["page"] <= rng[1] and (best is None or rng[1] - rng[0] < best[0]):
                        best = (rng[1] - rng[0], cand, d)
                if best:
                    _, doc_id, en_doc = best
            if not doc_id:
                out["note"] = "Could not find that issue and page on wol.jw.org automatically; the search link opens the citation there."
                out["links"]["en"] = out["links"]["search"]
                return out
        elif ref["kind"] == "lesson":
            doc_id = self._lesson_doc_id(ref["pub"], ref["lesson"], "en") or self._lesson_doc_id(ref["pub"], ref["lesson"], "chk")
            if not doc_id:
                out["note"] = "Lesson not found on wol.jw.org."
                out["links"]["en"] = pub_index_url(ref["pub"], "en")
                return out
            en_doc = self._doc(doc_id, "en")
        elif ref["kind"] == "chapter":
            doc_id = self._chapter_doc_id(ref["pub"], ref["chapter"], "en")
            if not doc_id:
                out["note"] = "Chapter not found on wol.jw.org."
                out["links"]["en"] = pub_index_url(ref["pub"], "en")
                return out
            en_doc = self._doc(doc_id, "en")
        else:
            out["links"]["en"] = pub_index_url(ref["pub"], "en")
            out["note"] = "Insight is not available in Chuukese; the link opens the English volume."
            return out

        out["links"]["en"] = doc_url(doc_id, "en")
        chk_doc = self._doc(doc_id, "chk")
        if chk_doc:
            out["chuukese_available"] = True
            out["links"]["chk"] = doc_url(doc_id, "chk")
            out["title"]["chk"] = chk_doc["title"]
        else:
            out["note"] = "This article is not available in Chuukese."
        if en_doc:
            out["title"]["en"] = en_doc["title"]

        # The cited paragraphs (all of them when none is cited), English first.
        if en_doc:
            en_paras = paragraphs_by_number(en_doc["paragraphs"], wanted) if wanted else [(n or i + 1, pid, t) for i, (pid, t, n) in enumerate(en_doc["paragraphs"]) if len(t) > 40][:40]
            chk_by_pid = {pid: t for pid, t, _ in chk_doc["paragraphs"]} if chk_doc else {}
            chk_by_num = {n: t for n, _, t in paragraphs_by_number(chk_doc["paragraphs"], wanted)} if (chk_doc and wanted) else {}
            for number, pid, text in en_paras:
                chk_text = chk_by_num.get(number) or chk_by_pid.get(pid) if chk_doc else None
                glosses = self.glosser(chk_text) if (self.glosser and chk_text) else None
                hl = highlight_paragraph(text, chk_text, keys, glosses)
                out["paragraphs"].append({"number": number, "pid": pid, "en": text, "chk": chk_text, "en_sentences": hl["english"], "chk_sentences": hl["chuukese"]})
            if wanted and not out["paragraphs"]:
                out["note"] = (out["note"] + " " if out["note"] else "") + "The cited paragraph numbers were not found in the article."
        elif chk_doc:
            for number, pid, text in paragraphs_by_number(chk_doc["paragraphs"], wanted):
                out["paragraphs"].append({"number": number, "pid": pid, "en": None, "chk": text, "en_sentences": [], "chk_sentences": [{"text": s, "hit": False, "english_indices": [], "words": mark_words(s, [])} for s in split_sentences(text)]})
        return out


__all__ = ["CITATION_RE", "find_references", "key_words", "highlight_paragraph", "Resolver", "parse_document", "page_range", "paragraphs_by_number"]
