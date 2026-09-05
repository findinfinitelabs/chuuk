from __future__ import annotations

"""
Watchtower Online Library (WOL) search for Chuukese.

Scrapes the Chuukese WOL search endpoint (r303/lp-te) and returns the full
sentence around each hit, with the matched term marked, a citation, a publication
date for sorting, and a deep link back to the source paragraph.

WOL result markup, as of this writing::

    ul.results.resultContentDocument
      li.caption > a.lnk[href]      article title + link
      li.result > ul.resultItems
        li.searchResult             one per snippet
          article > div.document > p        the sentence; hits are <span class="mk">
        li.ref                      citation, e.g. "w01 4/1 p. 26-31 - Ewe Leenien Mas—2001"

Two entry points:
  search()        sentences containing a word or phrase, newest first
  verb_examples() same, plus the subject of the verb in each example
"""

import re
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

WOL_BASE = "https://wol.jw.org"
WOL_SEARCH = WOL_BASE + "/{lang}/wol/s/r303/lp-te"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "chk,en;q=0.9",
    "Connection": "keep-alive",
}

# Invisible characters WOL sprinkles through its markup.
_INVISIBLE = re.compile(r"[​‌‍­﻿⁠]")

# ---------------------------------------------------------------------------
# Subject markers
# ---------------------------------------------------------------------------
# Chuukese marks the subject with a proclitic before the verb; the form also
# encodes tense/polarity. Mirrors the `pronouns` table in
# frontend/src/data/grammarData.json, which drives the Verbs page — keep the two
# in step if either changes.
_PRONOUN_ROWS = [
    # english,        standalone, pastPresent, future,   indefinite, simpleNeg, emphaticNeg
    ("I", "ngang", "ua", "upwe", "upwap", "use", "usap"),
    ("you (sg.)", "en", "ka", "kopwe", "kopwap", "kose", "kosap"),
    ("he/she/it", "i", "a", "epwe", "ese", "ese", "esap"),
    ("we (incl.)", "kich", "sia", "sipwe", "sipwap", "sise", "sisap"),
    ("we (excl.)", "am", "aua", "aupwe", "aupwap", "ause", "ausap"),
    ("you (pl.)", "ami", "oua", "oupwe", "oupwap", "ouse", "ousap"),
    ("they", "ir", "ra", "repwe", "repwap", "rese", "resap"),
]

_TENSE_LABELS = ["Past/Present", "Future", "Indefinite", "Simple Negative", "Emphatic Negative"]

# marker form -> (english subject, tense label)
_SUBJECT_MARKERS: dict[str, tuple[str, str]] = {}
# standalone pronoun -> english subject
_STANDALONE: dict[str, str] = {}
for _row in _PRONOUN_ROWS:
    _english, _standalone = _row[0], _row[1]
    _STANDALONE[_standalone] = _english
    for _idx, _form in enumerate(_row[2:]):
        # "ese" is both he/she/it indefinite and simple-negative; first write wins.
        _SUBJECT_MARKERS.setdefault(_form, (_english, _TENSE_LABELS[_idx]))

# Possessive determiners (config/data/grammar/language_guide.json →
# pronouns.standAlonePossessives). A verb preceded by one of these is nominalised
# — "ach tongei" is "our love", not "we love" — so it is reported as a possessive
# rather than a subject.
_POSSESSIVES = {
    "ái": "my", "óm": "your", "an": "his/her/its", "ach": "our (incl.)",
    "ám": "our (excl.)", "ámi": "your (pl.)", "ar": "their",
    "nei": "my", "noum": "your", "néún": "his/her/its", "néúch": "our (incl.)",
    "néúm": "our (excl.)", "néúmi": "your (pl.)", "néúr": "their",
}

# Frequent function words that are capitalised sentence-initially and would
# otherwise be mistaken for names.
_PARTICLES = {
    "iwe", "nge", "pwe", "me", "ren", "are", "atun", "lón", "chok", "fókkun",
    "pwal", "ika", "nupwen", "mi", "we", "ewe", "ekkewe", "ei", "een", "eú",
    "usun", "ussun", "ina", "lupwen", "seni", "ngeni", "fán", "won", "lap",
}

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _clean(text: str) -> str:
    """Strip invisible characters and normalise whitespace."""
    text = _INVISIBLE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _pub_code_year(code: str) -> int | None:
    """Derive a year from a publication code such as 'w01', 'w97', 'mwb17'."""
    m = re.search(r"(\d{2,4})$", code)
    if not m:
        return None
    digits = m.group(1)
    if len(digits) == 4:
        return int(digits)
    if len(digits) == 2:
        n = int(digits)
        # WOL's Chuukese corpus starts in the 1980s, so 90+ is 19xx.
        return 1900 + n if n >= 90 else 2000 + n
    return None


def parse_reference(ref_text: str) -> dict:
    """Pull publication, date and pages out of a WOL citation line.

    Handles the shapes WOL actually emits::

        "w01 4/1 p. 26-31 - Ewe Leenien Mas—2001"   → Watchtower, 2001-04-01
        "mwb17 February p. 6 - ...—2017"            → 2017-02
        "nwt Föför 1:1-28:31 - Paipelin Ótót Séfé"  → undated
    """
    ref_text = _clean(ref_text)
    out: dict = {
        "raw": ref_text,
        "pub": None,
        "year": None,
        "month": None,
        "day": None,
        "pages": None,
        "title": None,
    }
    if not ref_text:
        return out

    # Split "citation - Publication Title—YEAR" on the first " - ".
    head, _, tail = ref_text.partition(" - ")
    out["title"] = tail.strip() or None

    tokens = head.split()
    if tokens:
        out["pub"] = tokens[0]

    # Year: prefer the trailing year on the title (—2001), else the pub code.
    year = None
    if tail:
        ym = re.search(r"[—–-]\s*(\d{4})\s*$", tail)
        if ym:
            year = int(ym.group(1))
    if year is None and out["pub"]:
        year = _pub_code_year(out["pub"])
    out["year"] = year

    # Issue date: "4/1" (month/day) directly after the pub code.
    if len(tokens) > 1:
        dm = re.match(r"^(\d{1,2})/(\d{1,2})$", tokens[1])
        if dm:
            out["month"], out["day"] = int(dm.group(1)), int(dm.group(2))
        else:
            name = _MONTHS.get(tokens[1].lower())
            if name:
                out["month"] = name

    pm = re.search(r"\bp\.\s*([\d,\s-]+)", head)
    if pm:
        out["pages"] = pm.group(1).strip()

    return out


def _sort_key(ref: dict) -> tuple:
    """Newest first. The leading flag parks undated material (Bible, songbook,
    reference works) behind everything that carries a date, in both directions."""
    year = ref.get("year")
    if not year:
        return (0, 0, 0, 0)
    return (1, year, ref.get("month") or 0, ref.get("day") or 0)


def _segments(node) -> list[dict]:
    """Flatten a snippet into ordered text runs, flagging the matched term.

    Returns e.g. [{"text": "ua aucheani ir ", "match": False},
                  {"text": "chapur", "match": True}, ...]

    Emitting segments rather than HTML keeps the caller free of
    dangerouslySetInnerHTML while preserving WOL's own idea of what matched —
    which is more reliable than re-matching, since WOL highlights inflected and
    accented variants of the query.
    """
    segs: list[dict] = []

    def walk(el, inside_match: bool):
        for child in el.children:
            name = getattr(child, "name", None)
            if name is None:
                text = _INVISIBLE.sub("", str(child))
                if text:
                    segs.append({"text": text, "match": inside_match})
            else:
                classes = child.get("class") or []
                walk(child, inside_match or "mk" in classes)

    walk(node, False)

    # Merge neighbours of the same kind and normalise whitespace.
    merged: list[dict] = []
    for seg in segs:
        if merged and merged[-1]["match"] == seg["match"]:
            merged[-1]["text"] += seg["text"]
        else:
            merged.append(dict(seg))
    for seg in merged:
        seg["text"] = re.sub(r"\s+", " ", seg["text"])
    while merged and not merged[0]["text"].strip():
        merged.pop(0)
    while merged and not merged[-1]["text"].strip():
        merged.pop()
    if merged:
        merged[0]["text"] = merged[0]["text"].lstrip()
        merged[-1]["text"] = merged[-1]["text"].rstrip()
    return [s for s in merged if s["text"]]


_WORD_RE = re.compile(r"[A-Za-zÀ-ÿÁáÉéÍíÓóÚúÑñÖöÜüŎŏÊê’'-]+")


def detect_subject(text_before: str) -> dict | None:
    """Identify the subject of a verb from the words immediately preceding it.

    Chuukese puts a subject proclitic directly before the verb ("a chapur" =
    he/she/it ...), so the last word before the hit is the primary signal. A
    capitalised word in that slot is reported as a named subject.
    """
    words = _WORD_RE.findall(text_before or "")
    if not words:
        return None

    last = words[-1]
    key = last.lower().strip("’'-")

    marker = _SUBJECT_MARKERS.get(key)
    if marker:
        english, tense = marker
        subject = {"subject": english, "marker": last, "tense": tense, "kind": "pronoun"}
        # A standalone pronoun or a name may sit in front of the marker:
        # "I a ..." / "Paulus a ..."
        if len(words) > 1:
            prev = words[-2]
            prev_key = prev.lower().strip("’'-")
            if prev_key in _STANDALONE:
                subject["standalone"] = prev
            elif (
                prev[:1].isupper()
                and prev_key not in _PARTICLES
                and prev_key not in _POSSESSIVES
            ):
                # "Tafit a tongei" — the marker still gives the tense, but the
                # named subject is the more useful label.
                subject["subject"] = prev
                subject["kind"] = "name"
        return subject

    if key in _STANDALONE:
        return {"subject": _STANDALONE[key], "marker": last, "tense": None, "kind": "pronoun"}

    if key in _POSSESSIVES:
        return {
            "subject": _POSSESSIVES[key],
            "marker": last,
            "tense": None,
            "kind": "possessive",
        }

    # A capitalised word reads as a name only when it is neither a known function
    # word nor merely the capitalised first word of the snippet.
    if last[:1].isupper() and len(words) > 1 and key not in _PARTICLES:
        return {"subject": last, "marker": last, "tense": None, "kind": "name"}

    return None


class WOLSearch:
    """Search the Chuukese Watchtower Online Library."""

    def __init__(self, language: str = "chk", session: requests.Session | None = None):
        self.language = language
        self.session = session or requests.Session()
        self.session.headers.update(_HEADERS)

    # -- fetching ----------------------------------------------------------
    def _fetch(self, query: str, page: int, timeout: int) -> str:
        url = WOL_SEARCH.format(lang=self.language) + f"?q={quote(query)}"
        if page > 1:
            url += f"&pg={page}"
        resp = self.session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text

    # -- parsing -----------------------------------------------------------
    def _parse(self, html: str, query: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[dict] = []

        for group in soup.select("ul.results.resultContentDocument"):
            caption = group.select_one("li.caption a.lnk")
            title = _clean(caption.get_text(" ", strip=True)) if caption else None
            href = caption.get("href") if caption else None
            link = urljoin(WOL_BASE, href) if href else None

            ref_el = group.select_one("li.ref")
            reference = parse_reference(ref_el.get_text(" ", strip=True) if ref_el else "")

            for item in group.select("li.searchResult"):
                document = item.select_one("div.document")
                if not document:
                    continue
                for para in document.find_all("p", recursive=False) or [document]:
                    segments = _segments(para)
                    if not segments:
                        continue
                    text = "".join(s["text"] for s in segments)
                    if len(text) < 10 or not any(s["match"] for s in segments):
                        continue
                    results.append(
                        {
                            "text": text,
                            "segments": segments,
                            "title": title,
                            "link": link,
                            "reference": reference,
                            "citation": reference.get("raw"),
                            "query": query,
                        }
                    )
        return results

    # -- public API --------------------------------------------------------
    def search(
        self,
        query: str,
        pages: int = 2,
        sort: str = "newest",
        limit: int = 60,
        timeout: int = 45,
    ) -> dict:
        """Return sentences containing `query`, newest publication first.

        WOL returns roughly 40 snippets per page in relevance order and offers no
        date sort of its own, so several pages are pooled and sorted here.
        """
        query = (query or "").strip()
        if not query:
            return {"query": query, "results": [], "totalFound": 0, "pagesFetched": 0}

        collected: list[dict] = []
        seen: set[str] = set()
        fetched = 0
        for page in range(1, max(1, pages) + 1):
            try:
                html = self._fetch(query, page, timeout)
            except requests.RequestException:
                break
            fetched += 1
            page_results = self._parse(html, query)
            if not page_results:
                break
            for item in page_results:
                fingerprint = item["text"][:160]
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                collected.append(item)

        if sort == "newest":
            collected.sort(key=lambda r: _sort_key(r["reference"]), reverse=True)
        elif sort == "oldest":
            dated = [r for r in collected if r["reference"].get("year")]
            undated = [r for r in collected if not r["reference"].get("year")]
            dated.sort(key=lambda r: _sort_key(r["reference"]))
            collected = dated + undated

        return {
            "query": query,
            "results": collected[:limit],
            "totalFound": len(collected),
            "pagesFetched": fetched,
            "sort": sort,
        }

    def verb_examples(
        self,
        verb: str,
        pages: int = 2,
        limit: int = 60,
        timeout: int = 45,
    ) -> dict:
        """Return examples of `verb` with the subject of each occurrence."""
        found = self.search(verb, pages=pages, sort="newest", limit=limit, timeout=timeout)

        grouped: dict[str, int] = {}
        for item in found["results"]:
            before = ""
            for seg in item["segments"]:
                if seg["match"]:
                    break
                before += seg["text"]
            subject = detect_subject(before)
            item["subject"] = subject
            key = subject["subject"] if subject else "unknown"
            grouped[key] = grouped.get(key, 0) + 1

        found["verb"] = verb
        # A list, not a dict: Flask's jsonify sorts dict keys alphabetically,
        # which would throw away the most-frequent-first ordering.
        found["subjectCounts"] = [
            {"subject": name, "count": count}
            for name, count in sorted(grouped.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        return found


__all__ = ["WOLSearch", "detect_subject", "parse_reference"]
