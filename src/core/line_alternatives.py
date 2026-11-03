"""
Alternatives for a talk line: published Chuukese sentences that say something
close to a collected or machine-translated line, with their English.

Two sources, both searched by the line's key terms (its longest content
words, which are usually its rarest):

* wol.jw.org, through the same search the Watchtower Library page uses, with
  the English of each hit looked up from the English edition;
* the sentence pairs already stored in the app (phrases, analysed articles,
  corrected Conversation Builder lines), which cost no request to the site
  and still answer while wol.jw.org declines automated requests.

Hits are scored by how many content words they share with the line, so the
closest wording comes first.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# Chuukese function words that say nothing about a sentence's subject.
_STOP = set(
    "ewe ekewe ena ekkena ei ekkei eu och ach ami ämi ir iir ngang en kich kech i ia iei ina pwe pwal nge iwe ren ngeni "
    "seni lon non won me mi mwo chok chök fan fän usun are ika pun pwün ika ese esap rese resap sipwe sia sise ua üa "
    "upwe üpwe epwe repwe ka kopwe ke oupwe ou ra re a an ar om öm ai nei neu noum nöüm noun nöün kewe kana kena "
    "met meta ifa ika pwata met pwe ngeni ren me lon seni won fän usun pwal mwo mürin mwirin lupwen fansoun ekis unusen "
    "meinisin chomong eman emon efoch eu ruu ülüngat mine minne minen mettoch ekoch fokun kan sap ese esor wor "
    "the and that with this from they them their have will your what when which there were been about into also than "
    "then more most some such only over very just like make made does doing done being because before after while "
    "where those these should would could other each many much every both between through during without within".split()
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def content_words(text: str) -> list[str]:
    out, seen = [], set()
    for w in _WORD.findall((text or "").lower()):
        if len(w) >= 4 and w not in _STOP and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def key_terms(text: str, n: int = 3) -> list[str]:
    """The n longest content words of a line, in order of length."""
    words = content_words(text)
    return sorted(words, key=lambda w: (-len(w), words.index(w)))[:n]


def overlap(a: str, b: str) -> float:
    """Shared content words over the smaller set (0–1)."""
    wa, wb = set(content_words(a)), set(content_words(b))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _norm(text: str) -> str:
    return " ".join(_WORD.findall((text or "").lower()))


class Finder:
    def __init__(self, dict_db, wol=None):
        """dict_db: the DictionaryDB (phrases_collection, .db); wol: a WOLSearch or None."""
        self.dict_db = dict_db
        self.wol = wol

    # -- stored pairs --------------------------------------------------------

    def local(self, chk: str, terms: list[str], limit: int = 40) -> list[dict]:
        if not terms or self.dict_db is None:
            return []
        rx = [{"$regex": re.escape(t), "$options": "i"} for t in terms]
        out: list[dict] = []
        db = getattr(self.dict_db, "db", None)

        def add(c, e, source, reference="", link=None):
            c, e = (c or "").strip(), (e or "").strip()
            if c and e and _norm(c) != _norm(chk):
                out.append({"chk": c, "en": e, "source": source, "reference": reference, "link": link})

        try:
            col = getattr(self.dict_db, "phrases_collection", None)
            if col is not None:
                q = {"$or": [{f: r} for r in rx for f in ("chuukese_phrase", "chuukese_sentence", "chuukese")]}
                for r in col.find(q, {"chuukese_phrase": 1, "chuukese_sentence": 1, "chuukese": 1, "english_translation": 1, "english": 1, "source": 1, "reference": 1}).limit(limit):
                    add(r.get("chuukese_phrase") or r.get("chuukese_sentence") or r.get("chuukese"), r.get("english_translation") or r.get("english"), "library", r.get("reference") or r.get("source") or "")
        except Exception as e:
            log.warning("phrases lookup: %s", e)
        try:
            if db is not None:
                q = {"$or": [{"paragraph.sentences.text_only": r} for r in rx]}
                for doc in db["article_analysis_paragraphs"].find(q, {"paragraph.sentences.text_only": 1, "paragraph.sentences.english_text": 1, "article_title": 1, "title": 1, "url": 1}).limit(limit):
                    title = doc.get("article_title") or doc.get("title") or "analysed article"
                    for s in (doc.get("paragraph") or {}).get("sentences") or []:
                        t = s.get("text_only") or ""
                        if any(term in t.lower() for term in terms):
                            add(t, s.get("english_text"), "article", title, doc.get("url"))
        except Exception as e:
            log.warning("article sentences lookup: %s", e)
        try:
            if db is not None:
                for doc in db["conversation_phrases"].find({"mt": False, "$or": [{"chk": r} for r in rx]}, {"chk": 1, "en": 1}).limit(20):
                    add(doc.get("chk"), doc.get("en"), "conversation")
        except Exception as e:
            log.warning("conversation phrases lookup: %s", e)
        return out

    # -- wol.jw.org ----------------------------------------------------------

    def wol_hits(self, chk: str, terms: list[str], limit: int = 6) -> tuple[list[dict], bool]:
        """(alternatives, reachable): WOL search for the two strongest terms,
        then the single strongest when that finds nothing."""
        if not terms or self.wol is None:
            return [], False
        reachable = True
        hits: list[dict] = []
        for query in [" ".join(terms[:2]), terms[0]] if len(terms) > 1 else [terms[0]]:
            try:
                res = self.wol.search(query, pages=1, limit=20)
            except Exception as e:
                log.warning("wol search %r: %s", query, e)
                reachable = False
                break
            hits = [h for h in res.get("results", []) if _norm(h.get("text", "")) != _norm(chk)]
            if hits:
                break
        if not hits:
            return [], reachable
        hits.sort(key=lambda h: -overlap(chk, h.get("text", "")))
        hits = hits[:limit]
        try:
            english = self.wol.english_for_many(hits)
        except Exception as e:
            log.warning("wol english: %s", e)
            english = [None] * len(hits)
        out = []
        for h, e in zip(hits, english):
            out.append({"chk": h.get("text", ""), "en": (e or {}).get("text", ""), "source": "wol", "reference": h.get("citation") or (h.get("title") or ""), "link": h.get("link")})
        return out, reachable

    # -- together ------------------------------------------------------------

    def find(self, chk: str, limit: int = 10) -> dict:
        terms = key_terms(chk)
        local = self.local(chk, terms)
        wol, reachable = self.wol_hits(chk, terms)
        seen: set[str] = set()
        items = []
        for it in wol + local:
            it["score"] = round(overlap(chk, it["chk"]), 2)
            key = _norm(it["chk"])
            if key in seen or it["score"] == 0:
                continue
            seen.add(key)
            items.append(it)
        items.sort(key=lambda it: (-it["score"], it["source"] != "wol"))
        return {"terms": terms, "items": items[:limit], "wol_reachable": reachable, "wol_count": len(wol)}


__all__ = ["content_words", "key_terms", "overlap", "Finder"]
