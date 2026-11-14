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
import threading
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from src.core.sentence_align import align_paragraphs, align_sentences, paragraph_label
from src.utils.scripture_parser import split_sentences as _shared_split

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


# ---------------------------------------------------------------------------
# English equivalents
# ---------------------------------------------------------------------------
# A Chuukese WOL document and its English edition share a document id, and
# their paragraphs share `data-pid`s (Bible verses share span ids such as
# "v44-2-26-1"). So the English for a snippet is found by locating the snippet's
# paragraph in the Chuukese document and reading the same paragraph in English.

WOL_DOC = WOL_BASE + "/{lang}/wol/d/{rsconf}/{lib}/{doc_id}"
_LANGS = {"chk": ("r303", "lp-te"), "en": ("r1", "lp-e")}

_VERSE_ID = re.compile(r"^v(\d+)-(\d+)-(\d+)-\d+$")
# A sentence ends at . ! or ?, plus any closing quotes/brackets and a trailing
# parenthesised citation such as "(Lam. 3:40)", and the next starts with a capital.
_SENTENCE_END = re.compile(
    r"[.!?][”’\"')\]]*(?:\s+\([^()]{1,80}\))?(?=\s+[“‘\"\[]?[A-ZÀ-Þ])"
)


def doc_id_from_link(link: str | None) -> str | None:
    """'https://wol.jw.org/chk/wol/d/r303/lp-te/2000884?q=..' → '2000884'."""
    m = re.search(r"/wol/d/[^/]+/[^/]+/(\d+)", link or "")
    return m.group(1) if m else None


def _norm(text: str) -> str:
    """Letters and digits only, lowercased — for matching snippets to paragraphs."""
    return re.sub(r"[^\w]+", " ", _clean(text).lower()).strip()


def _split_sentences(text: str) -> list[str]:
    """Sentences with scripture citations kept whole (shared splitter)."""
    return _shared_split(text)




def _english_paragraph(chk_paragraphs: list[tuple], en_paragraphs: list[tuple], chk_pid) -> tuple:
    """(pid, text) of the English paragraph paired with Chuukese `chk_pid`,
    or (None, None)."""
    idx = next((i for i, (pid, _) in enumerate(chk_paragraphs) if pid == chk_pid), None)
    if idx is None:
        return None, None
    paired = align_paragraphs(
        [{"pid": pid, "text": t} for pid, t in chk_paragraphs],
        [{"pid": pid, "text": t} for pid, t in en_paragraphs],
    )[idx]
    if paired is None:
        return None, None
    en_pid, en_text = en_paragraphs[paired]
    chk_text = chk_paragraphs[idx][1]
    if en_pid == chk_pid or (paragraph_label(chk_text) and paragraph_label(chk_text) == paragraph_label(en_text)):
        return en_pid, en_text
    return None, None


def _plain(el) -> str:
    """Element text without footnote (*) and cross-reference (+) markers."""
    el = BeautifulSoup(str(el), "html.parser")
    for marker in el.select("a.fn, sup"):
        marker.decompose()
    # Bible cross-reference markers are "+" links; scripture citations in
    # articles share the class but carry the reference text, so keep those.
    for marker in el.select("a.b"):
        if marker.get_text(strip=True) == "+":
            marker.decompose()
    text = _clean(el.get_text(" ", strip=True))
    text = re.sub(r"\s+([,.;:!?’”)\]])", r"\1", text)
    return re.sub(r"([(\[“‘])\s+", r"\1", text)


def _verse_ref(book: str, verse_ids: list[str]) -> str | None:
    """['v44-2-26-1', 'v44-2-28-1'] + 'Acts' → 'Acts 2:26, 28'."""
    parts: list[tuple[int, int]] = []
    for vid in verse_ids:
        m = _VERSE_ID.match(vid)
        if m and (int(m.group(2)), int(m.group(3))) not in parts:
            parts.append((int(m.group(2)), int(m.group(3))))
    if not parts or not book:
        return None
    out, chapter = [], None
    for ch, vs in parts:
        out.append(f"{ch}:{vs}" if ch != chapter else str(vs))
        chapter = ch
    return f"{book} " + ", ".join(out)


class WOLSearch:
    """Search the Chuukese Watchtower Online Library."""

    def __init__(self, language: str = "chk", session: requests.Session | None = None):
        self.language = language
        self.session = session or requests.Session()
        self.session.headers.update(_HEADERS)
        self._doc_cache: dict[tuple[str, str], dict] = {}
        self._doc_lock = threading.Lock()

    # -- fetching ----------------------------------------------------------
    def _get(self, url: str, timeout: int) -> str:
        """One request to wol.jw.org through the shared circuit breaker: when
        the site is declining automated requests, fail at once instead of
        spending the timeout."""
        from src.core import wol_health  # noqa: PLC0415

        if not wol_health.available():
            raise requests.RequestException("wol.jw.org is declining automated requests at the moment")
        try:
            resp = self.session.get(url, timeout=timeout)
        except requests.RequestException:
            wol_health.record_failure()
            raise
        if getattr(resp, "status_code", 200) != 200 or not resp.text.strip():
            # An empty 202 is the site declining automated requests for a while.
            wol_health.record_failure()
            raise requests.RequestException(f"wol.jw.org answered {resp.status_code} with {len(resp.text)} bytes")
        wol_health.record_success()
        return resp.text

    def _fetch(self, query: str, page: int, timeout: int) -> str:
        url = WOL_SEARCH.format(lang=self.language) + f"?q={quote(query)}"
        if page > 1:
            url += f"&pg={page}"
        return self._get(url, timeout)

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
            doc_id = doc_id_from_link(link)

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
                    # Bible snippets carry their verse ids; the English edition
                    # uses the same ids, so they pin down the English verse.
                    verse_ids = [
                        v.get("id") for v in para.select("span.v[id]") if _VERSE_ID.match(v.get("id", ""))
                    ]
                    results.append(
                        {
                            "text": text,
                            "segments": segments,
                            "title": title,
                            "link": link,
                            "docId": doc_id,
                            "verseIds": verse_ids,
                            "reference": reference,
                            "citation": reference.get("raw"),
                            "query": query,
                        }
                    )
        return results

    # -- English equivalents ----------------------------------------------
    def _document(self, doc_id: str, lang: str, timeout: int) -> dict | None:
        """Fetch one WOL document as {title, citation, publication, paragraphs, verses}.

        Documents are cached: a search usually holds several snippets from the
        same article, and a reopened search asks for the same articles again.
        """
        key = (lang, doc_id)
        with self._doc_lock:
            if key in self._doc_cache:
                return self._doc_cache[key]

        rsconf, lib = _LANGS[lang]
        try:
            html = self._get(WOL_DOC.format(lang=lang, rsconf=rsconf, lib=lib, doc_id=doc_id), timeout)
        except requests.RequestException:
            return None

        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article") or soup
        title_el = soup.select_one("li.resultsNavigationSelected .navContent") or soup.find("h1")
        location = soup.select_one("li.documentLocation")
        parent = soup.select_one("#parentTitle")
        doc = {
            "title": _clean(title_el.get_text(" ", strip=True)) if title_el else None,
            "citation": _clean(location.get_text(" ", strip=True)) if location else None,
            "publication": (_clean(parent.get("value", "")) or None) if parent else None,
            "paragraphs": [
                (p.get("data-pid"), _plain(p)) for p in article.select("[data-pid]")
            ],
            "verses": {
                v["id"]: _plain(v) for v in article.select("span.v[id]") if _VERSE_ID.match(v["id"])
            },
        }
        # Bible chapters are titled with the book alone ("Acts").
        if doc["verses"] and soup.title:
            doc["book"] = _clean(soup.title.get_text().split("—")[0])

        with self._doc_lock:
            if len(self._doc_cache) >= 200:
                self._doc_cache.pop(next(iter(self._doc_cache)))
            self._doc_cache[key] = doc
        return doc

    def english_for(self, item: dict, timeout: int = 30) -> dict | None:
        """Find the English equivalent of one search result.

        Returns {text, scope, title, citation, publication, link} where scope is
        "sentence" when the English sentence(s) could be lined up with the
        Chuukese ones, "paragraph" when only the whole paragraph could, and
        "verse" for Bible text. None when the document has no English edition
        or the snippet could not be located.
        """
        doc_id = item.get("docId") or doc_id_from_link(item.get("link"))
        snippet = item.get("text") or ""
        if not doc_id or not snippet:
            return None

        english = self._document(doc_id, "en", timeout)
        if not english:
            return None
        meta = {
            "title": english["title"],
            "citation": english["citation"],
            "publication": english["publication"],
            "link": WOL_DOC.format(lang="en", rsconf="r1", lib="lp-e", doc_id=doc_id),
        }

        verse_ids = item.get("verseIds") or []
        if verse_ids and english["verses"]:
            text = " ".join(english["verses"][v] for v in verse_ids if v in english["verses"])
            if not text:
                return None
            ref = _verse_ref(english.get("book") or "", verse_ids)
            return {**meta, "text": text, "scope": "verse", "citation": ref or meta["citation"]}

        chuukese = self._document(doc_id, "chk", timeout)
        if not chuukese:
            return None

        # Locate the snippet's paragraph: containment first, then word overlap.
        target = _norm(snippet)
        target_words = set(target.split())
        best_pid, best_text, best_score = None, "", 0.0
        for pid, text in chuukese["paragraphs"]:
            norm = _norm(text)
            if target and target in norm:
                best_pid, best_text, best_score = pid, text, 1.0
                break
            if target_words:
                score = len(target_words & set(norm.split())) / len(target_words)
                if score > best_score:
                    best_pid, best_text, best_score = pid, text, score
        if best_pid is None or best_score < 0.6:
            return None

        # The English paragraph. Ids are shared between editions only until
        # one of them has an extra footnote, after which the same id names
        # different paragraphs; so the two paragraph lists are aligned as a
        # whole and a pair is trusted when its id or its study-question label
        # agrees.
        en_pid, en_para = _english_paragraph(chuukese["paragraphs"], english["paragraphs"], best_pid)
        if not en_para:
            return None
        meta["link"] += f"#h={en_pid}"

        # The English is returned as the whole paragraph, with the sentence(s)
        # that translate the snippet flagged. Sentences are paired by content
        # (citations, numbers, punctuation, length), so a reordered, split or
        # merged sentence still lands; with no pairing the whole paragraph shows.
        chk_sentences = _split_sentences(best_text)
        en_sentences = _split_sentences(en_para)
        match = None
        if chk_sentences and en_sentences:
            hits = []
            for i, sentence in enumerate(chk_sentences):
                norm = _norm(sentence)
                words = set(norm.split())
                if norm and (norm in target or target in norm):
                    hits.append(i)
                elif words and len(words & target_words) / len(words) >= 0.85:
                    hits.append(i)
            if hits:
                if len(chk_sentences) == 1 and len(en_sentences) == 1:
                    match = [0, 0]
                else:
                    paired = align_sentences(chk_sentences, en_sentences)
                    en_hits = sorted({e for i in hits for e in paired[i]})
                    if en_hits and en_hits != list(range(len(en_sentences))):
                        match = [en_hits[0], en_hits[-1]]

        return {
            **meta,
            "text": " ".join(en_sentences[match[0]: match[1] + 1]) if match else en_para,
            "sentences": en_sentences,
            "match": match,
            "scope": "sentence" if match else "paragraph",
        }

    def english_for_many(self, items: list[dict], timeout: int = 30, workers: int = 6) -> list[dict | None]:
        """english_for() over a batch, fetching documents in parallel."""
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda it: self.english_for(it, timeout=timeout), items))

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

    def count(self, query: str, recent_years: int = 3, timeout: int = 30) -> dict:
        """How often `query` occurs on wol.jw.org: one request for the first
        results page. The header's total ("Fán 2216") is the count across all
        years; wol.jw.org has no date filter, so the share from the last
        `recent_years` is estimated from the dated citations on that page."""
        import datetime as _dt  # noqa: PLC0415

        html = self._fetch(query, 1, timeout)
        soup = BeautifulSoup(html, "html.parser")
        for span in soup.select("span.count"):
            span.decompose()  # per-document "(Fán 6)" counts would be matched first
        text = _clean(soup.get_text(" "))
        m = re.search(r"Fán\s+([\d,.]+)", text) or re.search(r"([\d,.]+)\s+results?\b", text, re.IGNORECASE)
        total = int(re.sub(r"[^\d]", "", m.group(1))) if m else 0
        cutoff = _dt.date.today().year - recent_years
        years = [r["reference"].get("year") for r in self._parse(html, query) if (r.get("reference") or {}).get("year")]
        return {"query": query, "total": total, "recent": sum(1 for y in years if y >= cutoff), "sample": len(years), "since": cutoff + 1}

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


__all__ = ["WOLSearch", "detect_subject", "doc_id_from_link", "parse_reference"]
