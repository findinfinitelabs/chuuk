"""
Verb lookup: a Chuukese verb with its subject pronouns and object suffixes.

A Chuukese clause marks the subject with a proclitic in front of the verb
("ua álisi" = I help) and the object with a suffix on the verb ("álisuk" =
help you). This module builds both series for any verb in the dictionary:

* the subject series comes from a fixed table (the pronoun entries in the
  dictionary and ``grammarData.json`` agree on it);
* the object series is formed by rule and then checked against the dictionary,
  so each form says whether it is attested or only formed;
* examples are stored pairs (phrases, analysed articles, conversations) in
  which a subject marker stands directly before one of the forms.

Nothing here contacts wol.jw.org; the page offers that behind a button.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata

log = logging.getLogger(__name__)

# ── subject markers ─────────────────────────────────────────────────────────

TENSES = [
    ("past_present", "now / past", "{s} {v}"),
    ("future", "will", "{s} will {v}"),
    ("later", "shall, later", "{s} shall {v} later"),
    ("negative", "not", "{s} do not / did not {v}"),
    ("prohibitive", "must not", "{s} must not {v}"),
    ("not_yet", "not yet", "{s} have not yet {v}"),
    ("immediately", "right away", "{s} will {v} right away"),
]

PERSONS = [
    # id, english subject, stand-alone pronoun, markers per tense
    ("1s", "I", "ngang", ["ua", "upwe", "upwap", "use", "usap", "usaamwo", "upwele"]),
    ("2s", "you", "en", ["ka", "kopwe", "kopwap", "kose", "kosap", "kosaamwo", "kopwele"]),
    ("3s", "he / she / it", "i", ["a", "epwe", "epwap", "ese", "esap", "esaamwo", "epwele"]),
    ("1pi", "we (incl.)", "kich", ["sia", "sipwe", "sipwap", "sise", "sisap", "sisaamwo", "sipwele"]),
    ("1pe", "we (excl.)", "ám", ["aua", "aupwe", "aupwap", "ause", "ausap", "ausaamwo", "aupwele"]),
    ("2p", "you (pl.)", "ámi", ["oua", "oupwe", "oupwap", "ouse", "ousap", "ousaamwo", "oupwele"]),
    ("3p", "they", "ir", ["ra", "repwe", "repwap", "rese", "resap", "resaamwo", "repwele"]),
]

# Words that may stand between the marker and the verb.
ASPECTS = [("fen", "already"), ("kan", "usually"), ("chék", "just, only"), ("pwal", "also"), ("tongeni", "can")]

MARKER_INDEX: dict[str, tuple[str, str]] = {}
for _pid, _, _, _markers in PERSONS:
    for _t, _m in zip(TENSES, _markers):
        MARKER_INDEX[_m] = (_pid, _t[0])

# ── object suffixes ─────────────────────────────────────────────────────────

OBJECTS = [
    ("me", "me", "-ei"),
    ("you", "you", "-uk"),
    ("him", "him / her / it", "—"),
    ("us_incl", "us (incl.)", "-kich"),
    ("us_excl", "us (excl.)", "-kem"),
    ("you_pl", "you (pl.)", "-kemi"),
    ("them", "them", "-r"),
]


def rows(cursor_fn, attempts: int = 3) -> list:
    """Run a find and list it, retrying briefly on a Cosmos rate limit (429)."""
    for i in range(attempts):
        try:
            return list(cursor_fn())
        except Exception as e:
            if "429" not in str(e) and "RequestRateTooLarge" not in str(e) or i == attempts - 1:
                raise
            time.sleep(0.5 * (2 ** i))
    return []


def norm(word: str) -> str:
    """Lowercase, no accents, no hyphens: 'pwáseló' and 'pwaselo' compare equal."""
    d = unicodedata.normalize("NFD", (word or "").lower().replace("-", "").strip())
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def candidates(stem: str) -> dict[str, list[str]]:
    """Object forms by rule, most likely first. The dictionary decides which
    is attested; the first stays as the formed suggestion otherwise."""
    s = stem.strip()
    low = s.lower()
    out: dict[str, list[str]] = {}
    if low.endswith("ei"):
        out["me"] = [s[:-2] + "eei", s + "ei"]
        out["you"] = [s[:-2] + "eek", s + "uk", s[:-1] + "uk"]
        out["them"] = [s + "r", s + "ir"]
    elif low.endswith("i"):
        out["me"] = [s + "ei", s[:-1] + "ei"]
        out["you"] = [s + "uk", s[:-1] + "uk", s + "ók", s[:-1] + "ók"]
        out["them"] = [s + "ir", s + "r", s[:-1] + "ir"]
    else:
        out["me"] = [s + "ei", s + "iei"]
        out["you"] = [s + "uk", s + "iuk", s + "ók"]
        out["them"] = [s + "r", s + "ir", s + "er"]
    out["him"] = [s]
    out["us_incl"] = [s + "kich"]
    out["us_excl"] = [s + "kem"]
    out["you_pl"] = [s + "kemi"]
    return out


def _word_of(entry: dict) -> str:
    """'attauwei → attauweiei' entries name the derived form after the arrow."""
    w = (entry.get("chuukese_word") or "").strip()
    if "→" in w:
        w = w.split("→")[-1].strip()
    return w


def object_series(stem: str, related: list[dict]) -> list[dict]:
    """One row per object: the attested dictionary form when there is one,
    otherwise the first rule-formed candidate, flagged as formed."""
    by_norm: dict[str, dict] = {}
    for e in related:
        w = _word_of(e)
        if w:
            by_norm.setdefault(norm(w), e)
    rows = []
    for oid, english, suffix in OBJECTS:
        cands = candidates(stem).get(oid, [])
        hit = next(((c, by_norm[norm(c)]) for c in cands if norm(c) in by_norm), None)
        if hit:
            form, e = hit
            rows.append({"object": oid, "english": english, "suffix": suffix, "form": _word_of(e) or form, "attested": True,
                         "gloss": e.get("english_translation") or "", "alternatives": [c for c in cands if norm(c) != norm(form)]})
        else:
            rows.append({"object": oid, "english": english, "suffix": suffix, "form": cands[0] if cands else stem, "attested": False,
                         "gloss": "", "alternatives": cands[1:]})
    return rows


def other_forms(stem: str, related: list[dict], taken: set[str]) -> list[dict]:
    """Dictionary entries built on the stem that are not in the object series:
    directionals (-ló, -tá, -tiw, -to), reduplications, causatives."""
    out, seen = [], set()
    for e in related:
        w = _word_of(e)
        n = norm(w)
        if not w or n in taken or n in seen or n == norm(stem):
            continue
        seen.add(n)
        out.append({"form": w, "english": e.get("english_translation") or "", "modifier": e.get("grammar_modifier") or "", "grammar": e.get("grammar") or ""})
    return out[:40]


def subject_table(verb_form: str) -> list[dict]:
    return [
        {"person": pid, "english": english, "pronoun": pronoun,
         "cells": [{"tense": t[0], "marker": m, "chuukese": f"{m} {verb_form}"} for t, m in zip(TENSES, markers)]}
        for pid, english, pronoun, markers in PERSONS
    ]


# ── examples ────────────────────────────────────────────────────────────────

_ASPECT_WORDS = "|".join(re.escape(a) for a, _ in ASPECTS)


def clause_pattern(forms: list[str]) -> re.Pattern:
    markers = "|".join(sorted((re.escape(m) for m in MARKER_INDEX), key=len, reverse=True))
    alts = "|".join(re.escape(f) for f in sorted(set(forms), key=len, reverse=True) if f)
    return re.compile(rf"(?<![\w’'])({markers})\s+((?:(?:{_ASPECT_WORDS})\s+)*)({alts})(?![\w’'])", re.IGNORECASE)


def find_clause(text: str, pat: re.Pattern) -> dict | None:
    m = pat.search(text or "")
    if not m:
        return None
    marker = m.group(1).lower()
    pid, tense = MARKER_INDEX.get(marker, ("", ""))
    return {"marker": m.group(1), "aspect": m.group(2).strip(), "form": m.group(3), "person": pid, "tense": tense,
            "clause": m.group(0), "start": m.start(), "end": m.end()}


def examples_from_db(dict_db, forms: list[str], limit: int = 30) -> list[dict]:
    """Stored pairs in which a subject marker stands before one of `forms`."""
    if dict_db is None or not forms:
        return []
    pat = clause_pattern(forms)
    rx = [{"$regex": re.escape(f), "$options": "i"} for f in forms]
    out: list[dict] = []
    seen: set[str] = set()

    def add(c, e, source, reference=""):
        c, e = (c or "").strip(), (e or "").strip()
        if not c or norm(c) in seen:
            return
        hit = find_clause(c, pat)
        if not hit:
            return
        seen.add(norm(c))
        out.append({"chk": c, "en": e, "source": source, "reference": reference, **hit})

    db = getattr(dict_db, "db", None)
    try:
        col = getattr(dict_db, "phrases_collection", None)
        if col is not None:
            q = {"$or": [{f: r} for r in rx for f in ("chuukese_phrase", "chuukese_sentence", "chuukese")]}
            for r in rows(lambda: col.find(q, {"chuukese_phrase": 1, "chuukese_sentence": 1, "chuukese": 1, "english_translation": 1, "english": 1, "source": 1, "reference": 1}).limit(limit * 3)):
                add(r.get("chuukese_phrase") or r.get("chuukese_sentence") or r.get("chuukese"), r.get("english_translation") or r.get("english"), "library", r.get("reference") or r.get("source") or "")
    except Exception as e:  # pragma: no cover - network
        log.warning("verb examples, phrases: %s", e)
    try:
        if db is not None:
            q = {"$or": [{"paragraph.sentences.text_only": r} for r in rx]}
            for doc in rows(lambda: db["article_analysis_paragraphs"].find(q, {"paragraph.sentences.text_only": 1, "paragraph.sentences.english_text": 1, "article_title": 1, "title": 1, "url": 1}).limit(limit)):
                title = doc.get("article_title") or doc.get("title") or "analysed article"
                for s in (doc.get("paragraph") or {}).get("sentences") or []:
                    add(s.get("text_only"), s.get("english_text"), "article", title)
    except Exception as e:  # pragma: no cover
        log.warning("verb examples, articles: %s", e)
    try:
        if db is not None:
            for doc in rows(lambda: db["conversation_phrases"].find({"$or": [{"chk": r} for r in rx]}, {"chk": 1, "en": 1, "mt": 1}).limit(limit)):
                add(doc.get("chk"), doc.get("en"), "conversation (machine translated)" if doc.get("mt") else "conversation")
    except Exception as e:  # pragma: no cover
        log.warning("verb examples, conversations: %s", e)
    try:
        col = getattr(dict_db, "dictionary_collection", None)
        if col is not None:
            for doc in rows(lambda: col.find({"examples.0": {"$exists": True}, "$or": [{"examples": r} for r in rx]}, {"examples": 1, "chuukese_word": 1}).limit(limit)):
                for ex in doc.get("examples") or []:
                    text = ex if isinstance(ex, str) else (ex or {}).get("chuukese") or ""
                    en = "" if isinstance(ex, str) else (ex or {}).get("english") or ""
                    add(text, en, "dictionary example", doc.get("chuukese_word") or "")
    except Exception as e:  # pragma: no cover
        log.warning("verb examples, dictionary: %s", e)
    # Verified pairs first, machine-translated conversation fills last; shorter clauses read easier.
    out.sort(key=lambda x: (x["person"] == "", "machine" in x["source"], len(x["chk"])))
    return out[:limit]


# ── lookup ──────────────────────────────────────────────────────────────────

_PROJ = {"chuukese_word": 1, "english_translation": 1, "grammar": 1, "grammar_modifier": 1, "definition": 1, "_id": 0}


def _find_entry(col, query: str) -> dict | None:
    """Exact match first (accents ignored), verbs preferred; then a prefix match."""
    rx = re.compile(rf"^{re.escape(query)}", re.IGNORECASE)
    found = rows(lambda: col.find({"chuukese_word": {"$regex": rx.pattern, "$options": "i"}}, _PROJ).limit(60))
    if norm(query) != query.lower():
        found += rows(lambda: col.find({"chuukese_word": {"$regex": f"^{re.escape(norm(query))}", "$options": "i"}}, _PROJ).limit(60))
    exact = [r for r in found if norm(_word_of(r)) == norm(query)]
    exact.sort(key=lambda r: ((r.get("grammar") or "") != "verb", bool(r.get("grammar_modifier"))))
    if exact:
        return exact[0]
    verbs = [r for r in found if (r.get("grammar") or "") == "verb"]
    verbs.sort(key=lambda r: len(_word_of(r)))
    return verbs[0] if verbs else (found[0] if found else None)


_WORD_GRAMMARS = ("verb", "adjective", "adverb", "noun", "")


def english_matches(col, query: str, limit: int = 12) -> list[dict]:
    """Dictionary words (not phrases) whose English meaning contains `query`
    as a whole word, verbs first. 'need' → lamot, osun, osupwang."""
    pattern = rf"(^|[^a-z]){re.escape(query.lower())}([^a-z]|$)"
    found: list[dict] = []
    try:
        found = rows(lambda: col.find({"english_translation": {"$regex": pattern, "$options": "i"}}, _PROJ).limit(80))
    except Exception as e:  # pragma: no cover
        log.warning("verb lookup, english: %s", e)
    whole = re.compile(pattern, re.IGNORECASE)
    words = [r for r in found if _word_of(r) and len(_word_of(r).split()) <= 2 and (r.get("grammar") or "") in _WORD_GRAMMARS
             and whole.search(r.get("english_translation") or "")]
    order = {"verb": 0, "adjective": 1, "adverb": 2, "": 3, "noun": 4}
    words.sort(key=lambda r: (order.get(r.get("grammar") or "", 5), bool(r.get("grammar_modifier")), len(_word_of(r))))
    seen, out = set(), []
    for r in words:
        n = norm(_word_of(r))
        if n not in seen:
            seen.add(n)
            out.append({"chuukese": _word_of(r), "english": r.get("english_translation") or "", "grammar": r.get("grammar") or ""})
    return out[:limit]


def lookup(dict_db, query: str, example_limit: int = 30) -> dict:
    query = (query or "").strip()
    col = getattr(dict_db, "dictionary_collection", None) if dict_db is not None else None
    entry = _find_entry(col, query) if col is not None and query else None
    matches: list[dict] = []
    if col is not None and query and (entry is None or norm(_word_of(entry)) != norm(query)):
        # Not a Chuukese headword: treat the query as English and offer the words that mean it.
        matches = english_matches(col, query)
        if matches and (entry is None or re.fullmatch(r"[a-z\s'-]+", query.lower())):
            entry = _find_entry(col, matches[0]["chuukese"]) or {"chuukese_word": matches[0]["chuukese"], "english_translation": matches[0]["english"], "grammar": matches[0]["grammar"]}
    stem = _word_of(entry) if entry else query
    related: list[dict] = []
    if col is not None and stem:
        pats = {re.escape(stem[:-1] if len(stem) > 3 else stem)}
        n = norm(stem)
        pats.add(re.escape(n[:-1] if len(n) > 3 else n))
        try:
            for p in pats:
                related += rows(lambda: col.find({"chuukese_word": {"$regex": f"^{p}", "$options": "i"}}, _PROJ).limit(200))
        except Exception as e:  # pragma: no cover
            log.warning("verb lookup, related: %s", e)
    objects = object_series(stem, related)
    taken = {norm(o["form"]) for o in objects}
    others = other_forms(stem, related, taken)
    forms = [o["form"] for o in objects] + [o["form"] for o in others[:10]]
    return {
        "query": query,
        "found": entry is not None,
        "matches": matches,
        "verb": stem,
        "english": (entry or {}).get("english_translation") or "",
        "grammar": (entry or {}).get("grammar") or "",
        "modifier": (entry or {}).get("grammar_modifier") or "",
        "definition": (entry or {}).get("definition") or "",
        "persons": [{"id": pid, "english": en, "pronoun": pr} for pid, en, pr, _ in PERSONS],
        "tenses": [{"id": t, "label": lab, "gloss": g} for t, lab, g in TENSES],
        "aspects": [{"word": w, "english": e} for w, e in ASPECTS],
        "subjects": subject_table(stem),
        "objects": objects,
        "other_forms": others,
        "examples": examples_from_db(dict_db, forms, example_limit),
    }


__all__ = ["PERSONS", "TENSES", "OBJECTS", "ASPECTS", "MARKER_INDEX", "norm", "candidates", "object_series", "other_forms", "subject_table", "clause_pattern", "find_clause", "examples_from_db", "english_matches", "lookup"]
